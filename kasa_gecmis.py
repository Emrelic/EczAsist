"""
Botanik Bot - Kasa Geçmişi Modülü
Geçmiş kasa kayıtlarını görüntüleme ve takvim
Terminal modunda API üzerinden veri çeker
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

    def __init__(self, parent, db_cursor, db_conn, api_client=None):
        """
        parent: Ana pencere
        db_cursor: Veritabanı cursor
        db_conn: Veritabanı connection
        api_client: Terminal modunda API client (opsiyonel)
        """
        self.parent = parent
        self.cursor = db_cursor
        self.conn = db_conn
        self.api_client = api_client  # Terminal modunda kullanılır
        self.pencere = None
        self.secili_tarih = None
        self.gecmis_cache = []  # API'den çekilen veriler için cache

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
        """Kayıtlı tarihleri al - Terminal modunda API'den"""
        try:
            # Terminal modunda API'den al
            if self.api_client:
                success, result = self.api_client.kasa_gecmisi_al(limit=365)
                if success and result.get('success'):
                    self.gecmis_cache = result.get('data', [])
                    return {row.get('tarih') for row in self.gecmis_cache if row.get('tarih')}
                else:
                    logger.warning("Terminal: Kayıtlı tarihler API'den alınamadı")
                    return set()

            # Ana makine modunda yerel DB'den al
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
        """Son kayıtları yükle - Terminal modunda API'den"""
        try:
            self.tree.delete(*self.tree.get_children())

            rows = []

            # Terminal modunda API'den al
            if self.api_client:
                success, result = self.api_client.kasa_gecmisi_al(limit=30)
                if success and result.get('success'):
                    for row_data in result.get('data', []):
                        rows.append((
                            row_data.get('tarih'),
                            row_data.get('genel_toplam', 0),
                            row_data.get('fark', 0)
                        ))
                else:
                    logger.warning("Terminal: Son kayıtlar API'den alınamadı")
            else:
                # Ana makine modunda yerel DB'den al
                self.cursor.execute('''
                    SELECT tarih, genel_toplam, fark
                    FROM kasa_kapatma
                    ORDER BY id DESC
                    LIMIT 30
                ''')
                rows = self.cursor.fetchall()

            for row in rows:
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
        """Seçilen tarihin detayını göster - TÜM VERİLER"""
        # Önceki içeriği temizle
        for widget in self.detay_frame.winfo_children():
            widget.destroy()

        try:
            data = None

            # Terminal modunda API'den al
            if self.api_client:
                success, result = self.api_client.tarihe_gore_kasa_al(tarih)
                if success and result.get('success'):
                    kayitlar = result.get('data', [])
                    if kayitlar:
                        data = kayitlar[0]  # İlk kaydı al
                else:
                    logger.warning(f"Terminal: {tarih} için kayıt API'den alınamadı")
            else:
                # Ana makine modunda yerel DB'den al
                self.cursor.execute('''
                    SELECT * FROM kasa_kapatma WHERE tarih = ?
                ''', (tarih,))
                row = self.cursor.fetchone()

                if row:
                    # Sütun isimlerini al
                    self.cursor.execute("PRAGMA table_info(kasa_kapatma)")
                    columns = [col[1] for col in self.cursor.fetchall()]

                    # Row'u dict'e çevir
                    data = {}
                    for i, col in enumerate(columns):
                        if i < len(row):
                            data[col] = row[i]

            if not data:
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
                gun_isimleri = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
                gun_adi = gun_isimleri[dt.weekday()]
                tarih_gosterim = f"{gun_adi}, {dt.strftime('%d.%m.%Y')}"
            except Exception:
                tarih_gosterim = tarih

            saat = data.get('saat', '')
            self.detay_baslik.config(text=f"KASA DETAYI - {tarih_gosterim} {saat}", fg='#1565C0')

            # Scroll edilebilir alan
            canvas = tk.Canvas(self.detay_frame, bg='#FAFAFA', highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.detay_frame, orient="vertical", command=canvas.yview)
            scrollable = tk.Frame(canvas, bg='#FAFAFA')

            scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            def on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            canvas.bind_all("<MouseWheel>", on_mousewheel)

            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

            # Detay JSON
            detay = {}
            detay_json = data.get('detay_json')
            if detay_json:
                try:
                    detay = json.loads(detay_json)
                except json.JSONDecodeError:
                    pass

            # ========== 1) BAŞLANGIÇ KASASI ==========
            self.bolum_olustur(scrollable, "1) BAŞLANGIÇ KASASI", '#C8E6C9', [
                ("Başlangıç Kasası Toplam", data.get('baslangic_kasasi', 0), True)
            ])

            # Manuel başlangıç varsa göster
            manuel = detay.get('manuel_baslangic', {})
            if manuel.get('aktif'):
                self.bilgi_satir(scrollable, f"  * Manuel Giriş: {manuel.get('aciklama', '')}", '#FFF3E0')

            # ========== 2) GÜN SONU SAYIM ==========
            self.bolum_olustur(scrollable, "2) GÜN SONU NAKİT SAYIMI", '#C8E6C9', [
                ("Nakit Sayım Toplam", data.get('nakit_toplam', 0), True)
            ])

            # Küpür detayları
            sayim_kupurler = detay.get('sayim_kupurler', {})
            if sayim_kupurler:
                self.kupurler_detay_goster(scrollable, "Sayım Küpürleri", sayim_kupurler)

            # ========== 3) POS RAPORLARI ==========
            pos_detay = detay.get('pos', [])
            pos_satirlari = []

            # EczPOS (ilk 4)
            eczpos_toplam = 0
            for i, tutar in enumerate(pos_detay[:4]):
                if tutar and tutar > 0:
                    pos_satirlari.append((f"EczPOS {i+1}", tutar, False))
                    eczpos_toplam += tutar
            if eczpos_toplam > 0:
                pos_satirlari.append(("EczPOS Toplam", eczpos_toplam, True))

            # Ingenico (sonraki 4)
            ingenico_toplam = 0
            for i, tutar in enumerate(pos_detay[4:8]):
                if tutar and tutar > 0:
                    pos_satirlari.append((f"Ingenico {i+1}", tutar, False))
                    ingenico_toplam += tutar
            if ingenico_toplam > 0:
                pos_satirlari.append(("Ingenico Toplam", ingenico_toplam, True))

            pos_satirlari.append(("POS GENEL TOPLAM", data.get('pos_toplam', 0), True))
            self.bolum_olustur(scrollable, "3) POS RAPORLARI", '#BBDEFB', pos_satirlari)

            # ========== 4) IBAN ==========
            iban_detay = detay.get('iban', [])
            iban_satirlari = []
            for i, tutar in enumerate(iban_detay):
                if tutar and tutar > 0:
                    iban_satirlari.append((f"IBAN {i+1}", tutar, False))
            iban_satirlari.append(("IBAN TOPLAM", data.get('iban_toplam', 0), True))
            self.bolum_olustur(scrollable, "4) IBAN", '#BBDEFB', iban_satirlari)

            # ========== 5) GİRİLMEYEN MASRAFLAR ==========
            masraflar = detay.get('masraflar', [])
            masraf_satirlari = []
            for i, (tutar, aciklama) in enumerate(masraflar):
                if tutar and tutar > 0:
                    masraf_satirlari.append((f"M{i+1}: {aciklama[:20] if aciklama else '-'}", tutar, False))
            masraf_satirlari.append(("MASRAF TOPLAM", data.get('masraf_toplam', 0), True))
            self.bolum_olustur(scrollable, "5) GİRİLMEYEN MASRAFLAR (-)", '#FFF3E0', masraf_satirlari)

            # ========== 6) SİLİNEN REÇETE ETKİSİ ==========
            silinen = detay.get('silinen', [])
            silinen_satirlari = []
            for i, (tutar, aciklama) in enumerate(silinen):
                if tutar and tutar > 0:
                    silinen_satirlari.append((f"S{i+1}: {aciklama[:20] if aciklama else '-'}", tutar, False))
            silinen_satirlari.append(("SİLİNEN TOPLAM", data.get('silinen_etki_toplam', 0), True))
            self.bolum_olustur(scrollable, "6) SİLİNEN REÇETE ETKİSİ (-)", '#FFCDD2', silinen_satirlari)

            # ========== 7) ALINAN PARALAR ==========
            alinan = detay.get('gun_ici_alinan', [])
            alinan_satirlari = []
            for i, (tutar, aciklama) in enumerate(alinan):
                if tutar and tutar > 0:
                    alinan_satirlari.append((f"A{i+1}: {aciklama[:20] if aciklama else '-'}", tutar, False))
            alinan_satirlari.append(("ALINAN TOPLAM", data.get('gun_ici_alinan_toplam', 0), True))
            self.bolum_olustur(scrollable, "7) ALINAN PARALAR (+)", '#C8E6C9', alinan_satirlari)

            # ========== 8) GENEL TOPLAM ==========
            self.bolum_olustur(scrollable, "8) GENEL TOPLAM", '#E1BEE7', [
                ("Nakit + POS + IBAN", data.get('genel_toplam', 0), False),
                ("SON GENEL TOPLAM", data.get('son_genel_toplam', 0), True)
            ])

            # ========== 9) BOTANİK - SAYIM KARŞILAŞTIRMA ==========
            botanik_nakit = data.get('botanik_nakit', 0)
            botanik_pos = data.get('botanik_pos', 0)
            botanik_iban = data.get('botanik_iban', 0)
            botanik_toplam = data.get('botanik_genel_toplam', 0)

            # Düzeltilmiş nakit = nakit + masraf + silinen + alınan
            duzeltilmis_nakit = (data.get('nakit_toplam', 0) +
                                data.get('masraf_toplam', 0) +
                                data.get('silinen_etki_toplam', 0) +
                                data.get('gun_ici_alinan_toplam', 0))
            duzeltilmis_toplam = duzeltilmis_nakit + data.get('pos_toplam', 0) + data.get('iban_toplam', 0)

            nakit_fark = duzeltilmis_nakit - botanik_nakit
            pos_fark = data.get('pos_toplam', 0) - botanik_pos
            iban_fark = data.get('iban_toplam', 0) - botanik_iban
            genel_fark = data.get('fark', 0)

            fark_frame = tk.LabelFrame(scrollable, text="9) SAYIM - BOTANİK KARŞILAŞTIRMA",
                                       font=("Arial", 10, "bold"), bg='#FFF9C4', padx=10, pady=10)
            fark_frame.pack(fill="x", pady=5, padx=5)

            # Başlık satırı
            header = tk.Frame(fark_frame, bg='#FFF9C4')
            header.pack(fill="x")
            tk.Label(header, text="", width=12, bg='#FFF9C4', font=("Arial", 9, "bold")).pack(side="left")
            tk.Label(header, text="SAYIM", width=12, bg='#FFF9C4', font=("Arial", 9, "bold")).pack(side="left")
            tk.Label(header, text="BOTANİK", width=12, bg='#FFF9C4', font=("Arial", 9, "bold")).pack(side="left")
            tk.Label(header, text="FARK", width=12, bg='#FFF9C4', font=("Arial", 9, "bold")).pack(side="left")

            self.fark_satir(fark_frame, "Nakit", duzeltilmis_nakit, botanik_nakit, nakit_fark)
            self.fark_satir(fark_frame, "POS", data.get('pos_toplam', 0), botanik_pos, pos_fark)
            self.fark_satir(fark_frame, "IBAN", data.get('iban_toplam', 0), botanik_iban, iban_fark)

            ttk.Separator(fark_frame, orient='horizontal').pack(fill="x", pady=3)
            self.fark_satir(fark_frame, "TOPLAM", duzeltilmis_toplam, botanik_toplam, genel_fark, bold=True)

            # ========== 10) ERTESİ GÜN KASASI ==========
            self.bolum_olustur(scrollable, "10) ERTESİ GÜN KASASI", '#B2DFDB', [
                ("ERTESİ GÜN KASASI TOPLAM", data.get('ertesi_gun_kasasi', 0), True)
            ])

            # ========== 11) AYRILAN PARA ==========
            self.bolum_olustur(scrollable, "11) AYRILAN PARA", '#FFCCBC', [
                ("AYRILAN PARA TOPLAM", data.get('ayrilan_para', 0), True)
            ])

        except Exception as e:
            logger.error(f"Detay gösterme hatası: {e}")
            import traceback
            traceback.print_exc()
            tk.Label(
                self.detay_frame,
                text=f"Hata: {e}",
                font=("Arial", 10),
                bg='#FAFAFA',
                fg='#F44336'
            ).pack(pady=20)

    def bolum_olustur(self, parent, baslik, renk, satirlar):
        """Bölüm frame oluştur"""
        frame = tk.LabelFrame(parent, text=baslik, font=("Arial", 10, "bold"),
                             bg=renk, padx=10, pady=5)
        frame.pack(fill="x", pady=3, padx=5)

        for etiket, deger, bold in satirlar:
            row = tk.Frame(frame, bg=renk)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=etiket, font=("Arial", 9, "bold" if bold else "normal"),
                    bg=renk, anchor='w', width=25).pack(side="left")

            deger_text = f"{deger:,.2f} TL" if isinstance(deger, (int, float)) else str(deger)
            tk.Label(row, text=deger_text, font=("Arial", 9, "bold" if bold else "normal"),
                    bg=renk, anchor='e', width=15).pack(side="right")

    def bilgi_satir(self, parent, metin, renk):
        """Bilgi satırı ekle"""
        tk.Label(parent, text=metin, font=("Arial", 9, "italic"),
                bg=renk, anchor='w').pack(fill="x", padx=10)

    def fark_satir(self, parent, etiket, sayim, botanik, fark, bold=False):
        """Fark tablosu satırı"""
        row = tk.Frame(parent, bg='#FFF9C4')
        row.pack(fill="x", pady=1)

        font = ("Arial", 9, "bold" if bold else "normal")

        tk.Label(row, text=etiket, width=12, bg='#FFF9C4', font=font, anchor='w').pack(side="left")
        tk.Label(row, text=f"{sayim:,.0f}", width=12, bg='#FFF9C4', font=font).pack(side="left")
        tk.Label(row, text=f"{botanik:,.0f}", width=12, bg='#FFF9C4', font=font).pack(side="left")

        fark_renk = '#4CAF50' if abs(fark) < 0.01 else '#F44336' if fark < 0 else '#FF9800'
        fark_text = f"+{fark:,.0f}" if fark > 0 else f"{fark:,.0f}"
        tk.Label(row, text=fark_text, width=12, bg='#FFF9C4', font=font, fg=fark_renk).pack(side="left")

    def kupurler_detay_goster(self, parent, baslik, kupurler):
        """Küpür detaylarını göster"""
        if not kupurler:
            return

        frame = tk.Frame(parent, bg='#E8F5E9', padx=10, pady=5)
        frame.pack(fill="x", padx=15)

        kupur_degerleri = [200, 100, 50, 20, 10, 5, 1, 0.5]
        satir_text = []
        for deger in kupur_degerleri:
            adet = kupurler.get(str(deger), kupurler.get(str(int(deger)) if deger >= 1 else str(deger), 0))
            if adet and adet > 0:
                if deger >= 1:
                    satir_text.append(f"{int(deger)}TL x{adet}")
                else:
                    satir_text.append(f"50Kr x{adet}")

        if satir_text:
            tk.Label(frame, text="  ".join(satir_text), font=("Arial", 8),
                    bg='#E8F5E9', fg='#2E7D32').pack(anchor='w')

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
