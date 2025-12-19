"""
Botanik Bot - Kasa Geçmişi Modülü
Geçmiş kasa kayıtlarını görüntüleme ve takvim
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import json
from datetime import datetime, timedelta
import calendar

logger = logging.getLogger(__name__)


class KasaGecmisiPenceresi:
    """Kasa Geçmişi Görüntüleme Penceresi"""

    def __init__(self, parent, db_cursor, db_conn):
        """
        parent: Ana pencere
        db_cursor: Veritabanı cursor
        db_conn: Veritabanı connection
        """
        self.parent = parent
        self.cursor = db_cursor
        self.conn = db_conn
        self.pencere = None
        self.secili_tarih = None

    def goster(self):
        """Kasa geçmişi penceresini göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("Kasa Gecmisi")
        self.pencere.geometry("1200x700")
        self.pencere.transient(self.parent)
        self.pencere.configure(bg='#FAFAFA')

        # Pencereyi ortala
        self.pencere.update_idletasks()
        x = (self.pencere.winfo_screenwidth() - 1200) // 2
        y = (self.pencere.winfo_screenheight() - 700) // 2
        self.pencere.geometry(f"1200x700+{x}+{y}")

        # Başlık
        baslik_frame = tk.Frame(self.pencere, bg='#1565C0', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="KASA GECMISI",
            font=("Arial", 14, "bold"),
            bg='#1565C0',
            fg='white'
        ).pack(expand=True)

        # Ana içerik - Sol takvim, Sağ detay
        main_frame = tk.Frame(self.pencere, bg='#FAFAFA')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Sol panel - Takvim ve özet liste
        sol_panel = tk.Frame(main_frame, bg='#FAFAFA', width=400)
        sol_panel.pack(side="left", fill="y", padx=(0, 10))
        sol_panel.pack_propagate(False)

        # Takvim
        self.takvim_olustur(sol_panel)

        # Son kayıtlar listesi
        self.son_kayitlar_olustur(sol_panel)

        # Sağ panel - Detay
        self.sag_panel = tk.Frame(main_frame, bg='#FAFAFA')
        self.sag_panel.pack(side="left", fill="both", expand=True)

        # Detay başlığı
        self.detay_baslik = tk.Label(
            self.sag_panel,
            text="Bir tarih secin",
            font=("Arial", 12, "bold"),
            bg='#FAFAFA',
            fg='#666'
        )
        self.detay_baslik.pack(pady=10)

        # Detay içerik frame
        self.detay_frame = tk.Frame(self.sag_panel, bg='#FAFAFA')
        self.detay_frame.pack(fill="both", expand=True)

    def takvim_olustur(self, parent):
        """Takvim widget'ı oluştur"""
        takvim_frame = tk.LabelFrame(
            parent,
            text="Takvim",
            font=("Arial", 10, "bold"),
            bg='#FAFAFA',
            padx=10,
            pady=10
        )
        takvim_frame.pack(fill="x", pady=(0, 10))

        # Ay/Yıl navigasyonu
        nav_frame = tk.Frame(takvim_frame, bg='#FAFAFA')
        nav_frame.pack(fill="x", pady=5)

        self.takvim_yil = datetime.now().year
        self.takvim_ay = datetime.now().month

        tk.Button(
            nav_frame,
            text="<",
            font=("Arial", 10, "bold"),
            bg='#E3F2FD',
            width=3,
            command=self.onceki_ay
        ).pack(side="left")

        self.ay_label = tk.Label(
            nav_frame,
            text=self.ay_adi(self.takvim_ay) + " " + str(self.takvim_yil),
            font=("Arial", 11, "bold"),
            bg='#FAFAFA'
        )
        self.ay_label.pack(side="left", expand=True)

        tk.Button(
            nav_frame,
            text=">",
            font=("Arial", 10, "bold"),
            bg='#E3F2FD',
            width=3,
            command=self.sonraki_ay
        ).pack(side="right")

        # Takvim grid
        self.takvim_grid_frame = tk.Frame(takvim_frame, bg='#FAFAFA')
        self.takvim_grid_frame.pack(fill="x", pady=5)

        self.takvim_ciz()

    def ay_adi(self, ay):
        """Ay numarasından Türkçe ay adı"""
        aylar = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran",
                 "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]
        return aylar[ay]

    def onceki_ay(self):
        """Önceki aya git"""
        self.takvim_ay -= 1
        if self.takvim_ay < 1:
            self.takvim_ay = 12
            self.takvim_yil -= 1
        self.ay_label.config(text=self.ay_adi(self.takvim_ay) + " " + str(self.takvim_yil))
        self.takvim_ciz()

    def sonraki_ay(self):
        """Sonraki aya git"""
        self.takvim_ay += 1
        if self.takvim_ay > 12:
            self.takvim_ay = 1
            self.takvim_yil += 1
        self.ay_label.config(text=self.ay_adi(self.takvim_ay) + " " + str(self.takvim_yil))
        self.takvim_ciz()

    def takvim_ciz(self):
        """Takvim grid'ini çiz"""
        # Önceki içeriği temizle
        for widget in self.takvim_grid_frame.winfo_children():
            widget.destroy()

        # Gün başlıkları
        gunler = ["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]
        for i, gun in enumerate(gunler):
            tk.Label(
                self.takvim_grid_frame,
                text=gun,
                font=("Arial", 8, "bold"),
                bg='#E3F2FD',
                width=5
            ).grid(row=0, column=i, padx=1, pady=1)

        # Ay günleri
        cal = calendar.monthcalendar(self.takvim_yil, self.takvim_ay)

        # Kayıtlı tarihleri al
        kayitli_tarihler = self.kayitli_tarihleri_al()

        for row_idx, hafta in enumerate(cal):
            for col_idx, gun in enumerate(hafta):
                if gun == 0:
                    tk.Label(
                        self.takvim_grid_frame,
                        text="",
                        width=5,
                        bg='#FAFAFA'
                    ).grid(row=row_idx+1, column=col_idx, padx=1, pady=1)
                else:
                    tarih_str = f"{self.takvim_yil}-{self.takvim_ay:02d}-{gun:02d}"
                    bugun = datetime.now().strftime("%Y-%m-%d")

                    # Renk belirleme
                    if tarih_str == bugun:
                        bg_renk = '#FFEB3B'  # Bugün - sarı
                        fg_renk = '#000'
                    elif tarih_str in kayitli_tarihler:
                        bg_renk = '#4CAF50'  # Kayıtlı - yeşil
                        fg_renk = 'white'
                    else:
                        bg_renk = '#FAFAFA'
                        fg_renk = '#666'

                    btn = tk.Button(
                        self.takvim_grid_frame,
                        text=str(gun),
                        font=("Arial", 9),
                        bg=bg_renk,
                        fg=fg_renk,
                        width=4,
                        bd=1,
                        cursor='hand2' if tarih_str in kayitli_tarihler else 'arrow',
                        command=lambda t=tarih_str: self.tarih_sec(t)
                    )
                    btn.grid(row=row_idx+1, column=col_idx, padx=1, pady=1)

    def kayitli_tarihleri_al(self):
        """Kayıtlı tarihleri al"""
        try:
            self.cursor.execute('SELECT DISTINCT tarih FROM kasa_kapatma')
            rows = self.cursor.fetchall()
            return {row[0] for row in rows}
        except Exception as e:
            logger.error(f"Kayıtlı tarih alma hatası: {e}")
            return set()

    def son_kayitlar_olustur(self, parent):
        """Son kayıtlar listesi"""
        liste_frame = tk.LabelFrame(
            parent,
            text="Son Kayitlar",
            font=("Arial", 10, "bold"),
            bg='#FAFAFA',
            padx=5,
            pady=5
        )
        liste_frame.pack(fill="both", expand=True)

        # Treeview
        columns = ('tarih', 'genel', 'fark')
        self.tree = ttk.Treeview(liste_frame, columns=columns, show='headings', height=12)

        self.tree.heading('tarih', text='Tarih')
        self.tree.heading('genel', text='Genel Top.')
        self.tree.heading('fark', text='Fark')

        self.tree.column('tarih', width=100)
        self.tree.column('genel', width=100)
        self.tree.column('fark', width=80)

        scrollbar = ttk.Scrollbar(liste_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Tıklama event
        self.tree.bind('<<TreeviewSelect>>', self.kayit_secildi)

        # Verileri yükle
        self.son_kayitlari_yukle()

    def son_kayitlari_yukle(self):
        """Son kayıtları yükle"""
        try:
            self.tree.delete(*self.tree.get_children())

            self.cursor.execute('''
                SELECT tarih, genel_toplam, fark
                FROM kasa_kapatma
                ORDER BY id DESC
                LIMIT 30
            ''')

            for row in self.cursor.fetchall():
                tarih = row[0]
                genel = row[1] or 0
                fark = row[2] or 0

                # Tarihi formatla
                try:
                    dt = datetime.strptime(tarih, "%Y-%m-%d")
                    tarih_gosterim = dt.strftime("%d.%m.%Y")
                except Exception:
                    tarih_gosterim = tarih

                fark_text = f"+{fark:,.0f}" if fark > 0 else f"{fark:,.0f}"

                self.tree.insert('', 'end', values=(
                    tarih_gosterim,
                    f"{genel:,.0f}",
                    fark_text
                ), tags=(tarih,))

        except Exception as e:
            logger.error(f"Son kayıtlar yükleme hatası: {e}")

    def kayit_secildi(self, event):
        """Listeden kayıt seçildi"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            tarih = item['tags'][0] if item['tags'] else None
            if tarih:
                self.tarih_sec(tarih)

    def tarih_sec(self, tarih):
        """Tarih seçildi, detayı göster"""
        self.secili_tarih = tarih
        self.detay_goster(tarih)

    def detay_goster(self, tarih):
        """Seçilen tarihin detayını göster"""
        # Önceki içeriği temizle
        for widget in self.detay_frame.winfo_children():
            widget.destroy()

        try:
            self.cursor.execute('''
                SELECT * FROM kasa_kapatma WHERE tarih = ?
            ''', (tarih,))
            row = self.cursor.fetchone()

            if not row:
                tk.Label(
                    self.detay_frame,
                    text="Bu tarih icin kayit bulunamadi",
                    font=("Arial", 11),
                    bg='#FAFAFA',
                    fg='#F44336'
                ).pack(pady=50)
                return

            # Başlık güncelle
            try:
                dt = datetime.strptime(tarih, "%Y-%m-%d")
                tarih_gosterim = dt.strftime("%d %B %Y")
            except Exception:
                tarih_gosterim = tarih

            self.detay_baslik.config(text=f"Kasa Detayi - {tarih_gosterim}", fg='#1565C0')

            # Scroll edilebilir alan
            canvas = tk.Canvas(self.detay_frame, bg='#FAFAFA', highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.detay_frame, orient="vertical", command=canvas.yview)
            scrollable = tk.Frame(canvas, bg='#FAFAFA')

            scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

            # Sütun indeksleri (veritabanı şemasına göre)
            # id, tarih, saat, baslangic_kasasi, baslangic_kupurler_json,
            # sayim_toplam, pos_toplam, iban_toplam,
            # masraf_toplam, silinen_etki_toplam, gun_ici_alinan_toplam,
            # nakit_toplam, genel_toplam, son_genel_toplam,
            # botanik_nakit, botanik_pos, botanik_iban, botanik_genel_toplam,
            # fark, ertesi_gun_kasasi, ertesi_gun_kupurler_json,
            # detay_json, olusturma_zamani

            # Özet bilgiler
            ozet_frame = tk.Frame(scrollable, bg='#E3F2FD', padx=15, pady=15)
            ozet_frame.pack(fill="x", pady=5)

            # Row değerlerini al
            baslangic = row[3] if len(row) > 3 else 0
            nakit = row[11] if len(row) > 11 else 0
            pos = row[6] if len(row) > 6 else 0
            iban = row[7] if len(row) > 7 else 0
            genel = row[12] if len(row) > 12 else 0
            son_genel = row[13] if len(row) > 13 else genel
            botanik_toplam = row[17] if len(row) > 17 else 0
            fark = row[18] if len(row) > 18 else 0
            ertesi_gun = row[19] if len(row) > 19 else 0

            # İki sütunlu gösterim
            sol = tk.Frame(ozet_frame, bg='#E3F2FD')
            sol.pack(side="left", fill="both", expand=True)

            sag = tk.Frame(ozet_frame, bg='#E3F2FD')
            sag.pack(side="left", fill="both", expand=True)

            # Sol sütun
            self.detay_satir_ekle(sol, "Baslangic Kasasi", baslangic)
            self.detay_satir_ekle(sol, "Nakit Toplam", nakit)
            self.detay_satir_ekle(sol, "POS Toplam", pos)
            self.detay_satir_ekle(sol, "IBAN Toplam", iban)
            self.detay_satir_ekle(sol, "Genel Toplam", genel, bold=True)

            # Sağ sütun
            self.detay_satir_ekle(sag, "Son Genel Toplam", son_genel, bold=True)
            self.detay_satir_ekle(sag, "Botanik Toplam", botanik_toplam)

            fark_renk = '#4CAF50' if abs(fark) < 0.01 else '#F44336' if fark < 0 else '#FF9800'
            self.detay_satir_ekle(sag, "Fark", fark, renk=fark_renk, bold=True)
            self.detay_satir_ekle(sag, "Ertesi Gun Kasasi", ertesi_gun, bold=True)

            # Detay JSON varsa küpürleri göster
            detay_json = row[21] if len(row) > 21 else None
            if detay_json:
                try:
                    detay = json.loads(detay_json)
                    self.kupurler_goster(scrollable, detay)
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"Detay gösterme hatası: {e}")
            tk.Label(
                self.detay_frame,
                text=f"Hata: {e}",
                font=("Arial", 10),
                bg='#FAFAFA',
                fg='#F44336'
            ).pack(pady=20)

    def detay_satir_ekle(self, parent, etiket, deger, renk=None, bold=False):
        """Detay satırı ekle"""
        row = tk.Frame(parent, bg='#E3F2FD')
        row.pack(fill="x", pady=2)

        tk.Label(
            row,
            text=f"{etiket}:",
            font=("Arial", 10, "bold" if bold else "normal"),
            bg='#E3F2FD',
            anchor='w',
            width=18
        ).pack(side="left")

        deger_text = f"{deger:,.2f} TL" if isinstance(deger, (int, float)) else str(deger)
        tk.Label(
            row,
            text=deger_text,
            font=("Arial", 10, "bold" if bold else "normal"),
            bg='#E3F2FD',
            fg=renk or '#000',
            anchor='e',
            width=15
        ).pack(side="right")

    def kupurler_goster(self, parent, detay):
        """Küpür detaylarını göster"""
        sayim_kupurler = detay.get("sayim_kupurler", {})
        if not sayim_kupurler:
            return

        kupur_frame = tk.LabelFrame(
            parent,
            text="Kupur Detaylari",
            font=("Arial", 10, "bold"),
            bg='#FAFAFA',
            padx=10,
            pady=10
        )
        kupur_frame.pack(fill="x", pady=10, padx=5)

        kupur_degerleri = [200, 100, 50, 20, 10, 5, 1, 0.5]
        kupur_isimleri = {
            200: "200 TL", 100: "100 TL", 50: "50 TL", 20: "20 TL",
            10: "10 TL", 5: "5 TL", 1: "1 TL", 0.5: "50 Kr"
        }

        for deger in kupur_degerleri:
            adet = sayim_kupurler.get(str(deger), 0)
            if adet > 0:
                row = tk.Frame(kupur_frame, bg='#FAFAFA')
                row.pack(fill="x", pady=1)

                tk.Label(
                    row,
                    text=kupur_isimleri.get(deger, str(deger)),
                    font=("Arial", 9),
                    bg='#FAFAFA',
                    width=10,
                    anchor='w'
                ).pack(side="left")

                tk.Label(
                    row,
                    text=f"x {adet}",
                    font=("Arial", 9),
                    bg='#FAFAFA',
                    width=8
                ).pack(side="left")

                tk.Label(
                    row,
                    text=f"= {adet * deger:,.2f} TL",
                    font=("Arial", 9, "bold"),
                    bg='#FAFAFA',
                    anchor='e'
                ).pack(side="right")
