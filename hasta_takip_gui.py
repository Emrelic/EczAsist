"""
Hasta Takip & WhatsApp Mesaj Modülü - GUI

Ana sekmeler:
  1. Yazdırma Günü Gelen Hastalar     (tıklama → wa.me açar)
  2. Hasta Portföyü                    (geliş sıklığı, son geliş)
  3. Devamlılık Raporu                 (reçete adedi, kaç gün oldu)
  4. Ayarlar                           (mod, tolerans, saat, şablon)
  5. Gönderim Log                      (geçmiş mesajlar)
"""

import logging
import threading
import tkinter as tk
import urllib.parse
import webbrowser
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Optional  # noqa: F401 — method annotation

from hasta_takip_db import HastaTakipDB
from hasta_takip_kuyruk import HastaTakipAyarlari, MesajKuyrugu

logger = logging.getLogger(__name__)


class HastaTakipGUI:
    """Ana sekme — 5 alt sekme içerir."""

    def __init__(self, root: tk.Tk, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback

        self.root.title("Hasta Takip & WhatsApp Mesaj")
        self.root.geometry("1280x780")
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.root)
        except Exception:
            pass

        self.ayarlar = HastaTakipAyarlari.yukle()
        self.kuyruk = MesajKuyrugu()
        self.db: HastaTakipDB = None

        self.root.protocol("WM_DELETE_WINDOW", self._kapat)
        self._arayuz_olustur()

    # ----------------------------------------------------------------- UI
    def _arayuz_olustur(self):
        ust = tk.Frame(self.root, bg="#263238", height=50)
        ust.pack(fill="x")
        tk.Label(
            ust, text="👥 Hasta Takip & WhatsApp Mesaj",
            font=("Arial", 14, "bold"), bg="#263238", fg="white",
        ).pack(side="left", padx=15, pady=10)
        tk.Button(
            ust, text="Ana Menüye Dön", command=self._kapat,
            bg="#455A64", fg="white", bd=0, padx=12,
        ).pack(side="right", padx=15, pady=10)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Önce ayarlar sekmesi (var_mod vs. diğer sekmelerde kullanılıyor)
        self.sekme_ayarlar = self._sekme_ayarlar_olustur()
        self.sekme_yazdirma = self._sekme_yazdirma_olustur()
        self.sekme_portfoy = self._sekme_portfoy_olustur()
        self.sekme_devamlilik = self._sekme_devamlilik_olustur()
        self.sekme_rapor_bitis = self._sekme_rapor_bitis_olustur()
        self.sekme_log = self._sekme_log_olustur()

        self.notebook.add(self.sekme_yazdirma, text="📬 Yazdırma Günü Gelen")
        self.notebook.add(self.sekme_portfoy, text="📊 Hasta Portföyü")
        self.notebook.add(self.sekme_devamlilik, text="📅 Devamlılık")
        self.notebook.add(self.sekme_rapor_bitis, text="📑 Rapor Bitiş Takibi")
        self.notebook.add(self.sekme_ayarlar, text="⚙ Ayarlar")
        self.notebook.add(self.sekme_log, text="🧾 Gönderim Log")

        self.durum_bar = tk.Label(
            self.root, text="Hazır", anchor="w",
            bg="#ECEFF1", fg="#37474F", padx=10,
        )
        self.durum_bar.pack(fill="x", side="bottom")

        # Tüm sekmeler oluştuktan sonra kuyruğu ekrana yükle
        self._kuyruktan_yukle()

    # ================================================================= SEKME 1
    def _sekme_yazdirma_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")

        kontrol = tk.Frame(f, bg="white")
        kontrol.pack(fill="x", padx=10, pady=8)

        tk.Button(
            kontrol, text="🔄 Listeyi Yenile (DB)", command=self._yazdirma_yenile,
            bg="#1976D2", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="left", padx=(0, 8))

        self.lbl_sayac = tk.Label(
            kontrol, text="", font=("Arial", 10, "bold"),
            bg="white", fg="#37474F",
        )
        self.lbl_sayac.pack(side="left", padx=10)

        tk.Button(
            kontrol, text="✅ Seçilene Gönder", command=self._secilene_gonder,
            bg="#43A047", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="right", padx=4)
        tk.Button(
            kontrol, text="❌ İptal (seçili)", command=self._secili_iptal,
            bg="#E53935", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="right", padx=4)

        bol = tk.PanedWindow(f, orient="horizontal", sashrelief="raised", bg="white")
        bol.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Sol: kuyruktaki hastalar
        sol = tk.Frame(bol, bg="white")
        bol.add(sol, minsize=520)

        kols = ("hasta", "tc", "tel", "ilac_sayi", "ziyaret", "son_gelis", "gun", "takip", "planli")
        self.tv_yaz = ttk.Treeview(
            sol, columns=kols, show="headings", selectmode="browse",
        )
        for k, b, w, a in [
            ("hasta",      "Hasta",      190, "w"),
            ("tc",         "T.C. Kimlik",100, "center"),
            ("tel",        "Telefon",    100, "center"),
            ("ilac_sayi",  "İlaç",       45,  "center"),
            ("ziyaret",    "Ziyaret",    60,  "center"),
            ("son_gelis",  "Son Geliş",  90,  "center"),
            ("gun",        "Gün Önce",   65,  "center"),
            ("takip",      "Takipli",    55,  "center"),
            ("planli",     "Planlı",     90,  "center"),
        ]:
            self.tv_yaz.heading(k, text=b)
            self.tv_yaz.column(k, width=w, anchor=a)
        self.tv_yaz.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(sol, orient="vertical", command=self.tv_yaz.yview)
        self.tv_yaz.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_yaz.bind("<<TreeviewSelect>>", lambda e: self._secim_guncelle())

        # Kısayollar: Ctrl+Shift+C → TC, Ctrl+C → mesaj
        self.tv_yaz.bind("<Control-Shift-C>", lambda e: self._tc_kopyala())
        self.tv_yaz.bind("<Control-Shift-c>", lambda e: self._tc_kopyala())
        self.root.bind("<Control-Shift-C>", lambda e: self._tc_kopyala())
        self.root.bind("<Control-Shift-c>", lambda e: self._tc_kopyala())
        # Sağ tık menüsü: TC kopyala
        self.menu_yaz = tk.Menu(self.tv_yaz, tearoff=0)
        self.menu_yaz.add_command(label="📋 T.C. Kimlik No Kopyala (Ctrl+Shift+C)", command=self._tc_kopyala)
        self.menu_yaz.add_command(label="📋 Telefonu Kopyala", command=self._tel_kopyala)
        self.menu_yaz.add_command(label="📋 Hasta Adını Kopyala", command=self._ad_kopyala)
        self.tv_yaz.bind("<Button-3>", self._yaz_sagtik)

        # Sağ: mesaj önizleme + WA Web butonu
        sag = tk.Frame(bol, bg="#FAFAFA")
        bol.add(sag, minsize=480)

        tk.Label(
            sag, text="Mesaj Önizleme", font=("Arial", 11, "bold"),
            bg="#FAFAFA",
        ).pack(anchor="w", padx=12, pady=(10, 6))

        self.txt_mesaj = tk.Text(
            sag, wrap="word", font=("Consolas", 10),
            bg="white", relief="solid", bd=1,
        )
        self.txt_mesaj.pack(fill="both", expand=True, padx=12, pady=4)

        btn_frame = tk.Frame(sag, bg="#FAFAFA")
        btn_frame.pack(fill="x", padx=12, pady=8)

        tk.Button(
            btn_frame, text="📱 WhatsApp Web'de Aç ve Gönder",
            command=self._wa_ac, bg="#25D366", fg="white",
            bd=0, padx=16, pady=8, font=("Arial", 10, "bold"),
        ).pack(side="left")
        tk.Button(
            btn_frame, text="📋 Panoya Kopyala", command=self._panoya_kopyala,
            bg="#546E7A", fg="white", bd=0, padx=12, pady=8,
        ).pack(side="left", padx=8)

        self._kuyruk_sonuclari: list = []
        return f

    # ================================================================= SEKME 2
    def _sekme_portfoy_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")

        # ---- Filtre paneli ---------------------------------------------
        filt = tk.LabelFrame(
            f, text="Filtreler", bg="white", fg="#1976D2",
            font=("Arial", 10, "bold"), padx=10, pady=8,
        )
        filt.pack(fill="x", padx=10, pady=(8, 4))

        bugun = date.today()
        # Tarih aralığı
        tk.Label(filt, text="Reçete tarih aralığı:", bg="white").grid(row=0, column=0, sticky="w")
        self.var_pf_bas = tk.StringVar(value=(bugun.replace(year=bugun.year - 1)).isoformat())
        self.var_pf_bit = tk.StringVar(value=bugun.isoformat())
        tk.Entry(filt, textvariable=self.var_pf_bas, width=12).grid(row=0, column=1, padx=4)
        tk.Label(filt, text="—", bg="white").grid(row=0, column=2)
        tk.Entry(filt, textvariable=self.var_pf_bit, width=12).grid(row=0, column=3, padx=4)

        # Son geliş sonra
        tk.Label(filt, text="   Son geliş ≥:", bg="white").grid(row=0, column=4, sticky="w")
        self.var_pf_songelis = tk.StringVar(value="")
        tk.Entry(filt, textvariable=self.var_pf_songelis, width=12).grid(row=0, column=5, padx=4)
        tk.Label(filt, text="(YYYY-AA-GG, boş=filtresiz)", bg="white", fg="#9E9E9E", font=("Arial", 8)).grid(row=0, column=6, sticky="w")

        # Ziyaret min/max
        tk.Label(filt, text="Ziyaret sayısı:", bg="white").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_pf_min = tk.StringVar(value="")
        self.var_pf_max = tk.StringVar(value="")
        tk.Entry(filt, textvariable=self.var_pf_min, width=6).grid(row=1, column=1, sticky="w", pady=(6, 0))
        tk.Label(filt, text="≤ ≤", bg="white").grid(row=1, column=2, pady=(6, 0))
        tk.Entry(filt, textvariable=self.var_pf_max, width=6).grid(row=1, column=3, sticky="w", pady=(6, 0))

        # Telefonlu & takipli
        self.var_pf_tel = tk.BooleanVar(value=False)
        self.var_pf_takip = tk.BooleanVar(value=False)
        tk.Checkbutton(
            filt, text="Sadece telefonu olanlar", variable=self.var_pf_tel, bg="white",
        ).grid(row=1, column=4, sticky="w", pady=(6, 0), padx=(10, 4))
        tk.Checkbutton(
            filt, text="Sadece takipli", variable=self.var_pf_takip, bg="white",
        ).grid(row=1, column=5, sticky="w", pady=(6, 0), columnspan=2)

        # Yenile butonu + sayac
        btn_frame = tk.Frame(filt, bg="white")
        btn_frame.grid(row=2, column=0, columnspan=7, sticky="we", pady=(8, 0))
        tk.Button(
            btn_frame, text="🔄 Filtreyi Uygula / Yenile", command=self._portfoy_yukle,
            bg="#1976D2", fg="white", bd=0, padx=16, pady=6,
        ).pack(side="left")
        self.lbl_portfoy = tk.Label(btn_frame, text="", bg="white", fg="#455A64")
        self.lbl_portfoy.pack(side="left", padx=12)

        # ---- Liste + detay paneli --------------------------------------
        bol = tk.PanedWindow(f, orient="horizontal", sashrelief="raised", bg="white")
        bol.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        sol = tk.Frame(bol, bg="white")
        bol.add(sol, minsize=520)

        kols = ("hasta", "tel", "ziyaret", "recete", "ilk", "son", "gun", "takip")
        self.tv_portfoy = ttk.Treeview(
            sol, columns=kols, show="headings", selectmode="browse",
        )
        baslik = {
            "hasta": ("Hasta", 220, "w"),
            "tel": ("Telefon", 100, "center"),
            "ziyaret": ("Ziyaret", 60, "center"),
            "recete": ("Reçete", 60, "center"),
            "ilk": ("İlk Geliş", 90, "center"),
            "son": ("Son Geliş", 90, "center"),
            "gun": ("Gün Önce", 70, "center"),
            "takip": ("Takipli", 60, "center"),
        }
        for k, (b, w, a) in baslik.items():
            self.tv_portfoy.heading(k, text=b)
            self.tv_portfoy.column(k, width=w, anchor=a)
        self.tv_portfoy.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(sol, orient="vertical", command=self.tv_portfoy.yview)
        self.tv_portfoy.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_portfoy.bind("<<TreeviewSelect>>", lambda e: self._portfoy_hasta_detay())

        # Detay paneli — sağda Notebook
        sag = tk.Frame(bol, bg="#FAFAFA")
        bol.add(sag, minsize=560)

        self.lbl_pf_detay = tk.Label(
            sag, text="◀ Soldan bir hasta seçin",
            bg="#FAFAFA", fg="#607D8B",
            font=("Arial", 11, "bold"), anchor="w",
        )
        self.lbl_pf_detay.pack(fill="x", padx=10, pady=(10, 6))

        self.nb_detay = ttk.Notebook(sag)
        self.nb_detay.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Raporlar
        f_rap = tk.Frame(self.nb_detay, bg="white")
        self.tv_pf_rap = ttk.Treeview(
            f_rap, columns=("no", "tur", "tarih", "bitis", "kalan", "hastane"),
            show="headings",
        )
        for k, b, w in [
            ("no", "Rapor No", 90), ("tur", "Tür", 140),
            ("tarih", "Tarih", 90), ("bitis", "Bitiş", 90),
            ("kalan", "Bitiş kalan", 80), ("hastane", "Hastane", 150),
        ]:
            self.tv_pf_rap.heading(k, text=b)
            self.tv_pf_rap.column(k, width=w)
        self.tv_pf_rap.pack(fill="both", expand=True)
        self.nb_detay.add(f_rap, text="📋 Raporlar")

        # Yaklaşan yazdırma
        f_yaz = tk.Frame(self.nb_detay, bg="white")
        self.tv_pf_yaz = ttk.Treeview(
            f_yaz, columns=("urun", "bitis", "yazdirma", "kalan", "rapor"),
            show="headings",
        )
        for k, b, w in [
            ("urun", "İlaç", 220), ("bitis", "Bitiş", 90),
            ("yazdirma", "Yazdırma", 90), ("kalan", "Kalan Gün", 80),
            ("rapor", "Rapor No", 100),
        ]:
            self.tv_pf_yaz.heading(k, text=b)
            self.tv_pf_yaz.column(k, width=w)
        self.tv_pf_yaz.pack(fill="both", expand=True)
        self.nb_detay.add(f_yaz, text="📬 Yaklaşan/Geçen Yazdırmalar")

        # İlaç geçmişi
        f_il = tk.Frame(self.nb_detay, bg="white")
        self.tv_pf_il = ttk.Treeview(
            f_il, columns=("tarih", "urun", "adet", "bitis", "rapor"),
            show="headings",
        )
        for k, b, w in [
            ("tarih", "Reçete Tarihi", 100), ("urun", "İlaç", 250),
            ("adet", "Adet", 50), ("bitis", "Bitiş", 90),
            ("rapor", "Rapor No", 100),
        ]:
            self.tv_pf_il.heading(k, text=b)
            self.tv_pf_il.column(k, width=w)
        self.tv_pf_il.pack(fill="both", expand=True)
        self.nb_detay.add(f_il, text="💊 İlaç Geçmişi")

        return f

    # ================================================================= SEKME 3
    def _sekme_devamlilik_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")
        top = tk.Frame(f, bg="white")
        top.pack(fill="x", padx=10, pady=8)

        tk.Button(
            top, text="🔄 Yenile", command=self._devamlilik_yukle,
            bg="#1976D2", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="left")
        self.lbl_devam = tk.Label(top, text="", bg="white", fg="#455A64")
        self.lbl_devam.pack(side="left", padx=12)

        kols = ("hasta", "tel", "dogum", "recete", "son", "gun", "takip")
        self.tv_devam = ttk.Treeview(f, columns=kols, show="headings")
        for k, b, w, a in [
            ("hasta", "Hasta", 260, "w"),
            ("tel", "Telefon", 110, "center"),
            ("dogum", "Doğum", 100, "center"),
            ("recete", "Reçete Adedi", 100, "center"),
            ("son", "Son Reçete", 110, "center"),
            ("gun", "Kaç Gün Oldu", 110, "center"),
            ("takip", "Takipli", 70, "center"),
        ]:
            self.tv_devam.heading(k, text=b)
            self.tv_devam.column(k, width=w, anchor=a)
        self.tv_devam.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        sb = ttk.Scrollbar(self.tv_devam, orient="vertical", command=self.tv_devam.yview)
        self.tv_devam.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        return f

    # ================================================================= SEKME 4
    def _sekme_ayarlar_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")
        kanvas = tk.Canvas(f, bg="white", highlightthickness=0)
        scroll = ttk.Scrollbar(f, orient="vertical", command=kanvas.yview)
        icerik = tk.Frame(kanvas, bg="white")
        icerik.bind(
            "<Configure>",
            lambda e: kanvas.configure(scrollregion=kanvas.bbox("all")),
        )
        kanvas.create_window((0, 0), window=icerik, anchor="nw")
        kanvas.configure(yscrollcommand=scroll.set)
        kanvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scroll.pack(side="right", fill="y")

        def grup(baslik):
            g = tk.LabelFrame(
                icerik, text=baslik, bg="white", fg="#1976D2",
                font=("Arial", 10, "bold"), padx=12, pady=10,
            )
            g.pack(fill="x", pady=8, padx=4)
            return g

        # Gönderim modu
        g1 = grup("Gönderim Modu")
        self.var_mod = tk.StringVar(value=self.ayarlar.gonderim_modu)
        for kod, et in [
            ("anlik", "Anlık (her tarama sonrası hemen listele)"),
            ("pazartesi", "Pazartesi birleşik (hafta içi biriktir, pazartesi gönder)"),
            ("periyodik", "Periyodik (her X günde bir listele)"),
        ]:
            tk.Radiobutton(
                g1, text=et, variable=self.var_mod, value=kod,
                bg="white", anchor="w",
            ).pack(fill="x", anchor="w")

        self.var_periyot = tk.IntVar(value=self.ayarlar.periyot_gun)
        self.var_gonderim_gun = tk.IntVar(value=self.ayarlar.toplu_gonderim_gunu)
        fr = tk.Frame(g1, bg="white")
        fr.pack(fill="x", pady=(6, 0))
        tk.Label(fr, text="Periyot (gün):", bg="white").pack(side="left")
        tk.Spinbox(fr, from_=1, to=30, width=4, textvariable=self.var_periyot).pack(side="left", padx=4)
        tk.Label(fr, text="   Toplu gönderim günü:", bg="white").pack(side="left", padx=(16, 4))
        ttk.Combobox(
            fr, state="readonly", width=14,
            values=["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
        ).pack(side="left")
        # NOTE: combobox'ı sakla, açıkken seçimi var_gonderim_gun'e yaz
        self._cb_gun = fr.winfo_children()[-1]
        self._cb_gun.current(self.ayarlar.toplu_gonderim_gunu)
        self._cb_gun.bind("<<ComboboxSelected>>", lambda e: self.var_gonderim_gun.set(self._cb_gun.current()))

        # Tolerans
        g2 = grup("Tolerans")
        fr2 = tk.Frame(g2, bg="white")
        fr2.pack(fill="x")
        tk.Label(fr2, text="Hafta sonu tolerans (gün):", bg="white").grid(row=0, column=0, sticky="w")
        self.var_hs = tk.IntVar(value=self.ayarlar.hafta_sonu_tolerans_gun)
        tk.Spinbox(fr2, from_=0, to=14, width=4, textvariable=self.var_hs).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(fr2, text="   Rapor yazdırma tolerans (gün):", bg="white").grid(row=0, column=2, sticky="w", padx=(16, 4))
        self.var_rt = tk.IntVar(value=self.ayarlar.rapor_yazdirma_tolerans_gun)
        tk.Spinbox(fr2, from_=0, to=30, width=4, textvariable=self.var_rt).grid(row=0, column=3, sticky="w")
        tk.Label(fr2, text="   Eski kayıt gün (gürültü filtresi):", bg="white").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_eski = tk.IntVar(value=self.ayarlar.eski_kayit_gun)
        tk.Spinbox(fr2, from_=0, to=365, width=5, textvariable=self.var_eski).grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))

        # Filtreler
        g3 = grup("Filtreler")
        self.var_takipli = tk.BooleanVar(value=self.ayarlar.sadece_takipli)
        tk.Checkbutton(
            g3, text="Sadece Takipli Hastalar (Musteri.MusteriTakipli=1)",
            variable=self.var_takipli, bg="white", anchor="w",
        ).pack(fill="x", anchor="w")

        fr3 = tk.Frame(g3, bg="white")
        fr3.pack(fill="x", pady=(6, 0))
        tk.Label(fr3, text="Veri kaynağı:", bg="white").pack(side="left")
        self.var_kaynak = tk.StringVar(value=self.ayarlar.kaynak)
        for v in ("RECETE", "MEDULA", "BIRLESIK"):
            tk.Radiobutton(
                fr3, text=v, variable=self.var_kaynak, value=v, bg="white",
            ).pack(side="left", padx=6)

        # Çalışma saatleri
        g4 = grup("Çalışma Saatleri (dışında gönderim penceresi kapalı)")
        fr4 = tk.Frame(g4, bg="white")
        fr4.pack(fill="x")
        self.var_bas = tk.StringVar(value=self.ayarlar.calisma_baslangic)
        self.var_bit = tk.StringVar(value=self.ayarlar.calisma_bitis)
        tk.Label(fr4, text="Başlangıç:", bg="white").pack(side="left")
        tk.Entry(fr4, textvariable=self.var_bas, width=7).pack(side="left", padx=4)
        tk.Label(fr4, text="   Bitiş:", bg="white").pack(side="left")
        tk.Entry(fr4, textvariable=self.var_bit, width=7).pack(side="left", padx=4)

        # Eczane bilgisi
        g5 = grup("Eczane Bilgisi")
        fr5 = tk.Frame(g5, bg="white")
        fr5.pack(fill="x")
        self.var_ec_ad = tk.StringVar(value=self.ayarlar.eczane_adi)
        self.var_ec_tel = tk.StringVar(value=self.ayarlar.eczane_tel)
        tk.Label(fr5, text="Eczane Adı:", bg="white").grid(row=0, column=0, sticky="w")
        tk.Entry(fr5, textvariable=self.var_ec_ad, width=40).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(fr5, text="Telefon:", bg="white").grid(row=1, column=0, sticky="w", pady=(4, 0))
        tk.Entry(fr5, textvariable=self.var_ec_tel, width=40).grid(row=1, column=1, sticky="w", padx=4, pady=(4, 0))

        # Şablon
        g6 = grup("Mesaj Şablonu (placeholders: {hasta_adi} {ilac_listesi} {eczane_adi} {eczane_tel})")
        self.txt_sablon = tk.Text(g6, height=6, font=("Consolas", 10))
        self.txt_sablon.pack(fill="x")
        self.txt_sablon.insert("1.0", self.ayarlar.mesaj_sablonu)

        tk.Label(g6, text="İlaç satır formatı ({urun_adi}):", bg="white").pack(anchor="w", pady=(8, 2))
        self.var_satir = tk.StringVar(value=self.ayarlar.ilac_satir_formati)
        tk.Entry(g6, textvariable=self.var_satir, width=60).pack(anchor="w")

        # Rapor bitiş şablonu
        g7 = grup(
            "Rapor Bitiş Mesaj Şablonu "
            "(placeholders: {hasta_adi} {rapor_listesi} {eczane_adi} {eczane_tel})"
        )
        self.var_rb_uyari = tk.IntVar(value=self.ayarlar.rapor_bitis_uyari_gun)
        uy = tk.Frame(g7, bg="white")
        uy.pack(fill="x")
        tk.Label(uy, text="Varsayılan 'bitişe kalan gün':", bg="white").pack(side="left")
        tk.Spinbox(uy, from_=0, to=365, width=5, textvariable=self.var_rb_uyari).pack(side="left", padx=4)

        tk.Label(g7, text="Mesaj şablonu:", bg="white").pack(anchor="w", pady=(6, 2))
        self.txt_rb_sablon = tk.Text(g7, height=6, font=("Consolas", 10))
        self.txt_rb_sablon.pack(fill="x")
        self.txt_rb_sablon.insert("1.0", self.ayarlar.rapor_bitis_mesaj_sablonu)

        tk.Label(
            g7,
            text="Her tanı satırı formatı (placeholders: {rapor_kodu} {rapor_kod_aciklama} "
                 "{icd_kodu} {icd_aciklamasi} {baslama} {bitis} {kalan_gun} "
                 "{etkin_maddeler} {ilaclar}):",
            bg="white", fg="#607D8B", font=("Arial", 8), wraplength=700, justify="left",
        ).pack(anchor="w", pady=(8, 2))
        self.txt_rb_tani_sablon = tk.Text(g7, height=6, font=("Consolas", 10))
        self.txt_rb_tani_sablon.pack(fill="x")
        self.txt_rb_tani_sablon.insert("1.0", self.ayarlar.rapor_bitis_tani_satir_formati)

        # Kaydet
        tk.Button(
            icerik, text="💾 Ayarları Kaydet", command=self._ayarlari_kaydet,
            bg="#1976D2", fg="white", bd=0, padx=20, pady=10,
            font=("Arial", 11, "bold"),
        ).pack(pady=16)

        return f

    # ================================================================= SEKME RAPOR BITIS
    def _sekme_rapor_bitis_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")

        # Üst filtre satırı
        top = tk.Frame(f, bg="white")
        top.pack(fill="x", padx=10, pady=8)

        tk.Label(top, text="Bitişe kalan (gün):", bg="white").pack(side="left")
        self.var_rb_gun = tk.IntVar(value=self.ayarlar.rapor_bitis_uyari_gun)
        tk.Spinbox(top, from_=0, to=365, width=5, textvariable=self.var_rb_gun).pack(side="left", padx=4)

        tk.Label(top, text="   Geçmişten geri (gün):", bg="white").pack(side="left", padx=(10, 0))
        self.var_rb_geri = tk.IntVar(value=0)
        tk.Spinbox(top, from_=0, to=90, width=5, textvariable=self.var_rb_geri).pack(side="left", padx=4)

        self.var_rb_takipli = tk.BooleanVar(value=False)
        self.var_rb_telefonlu = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="Sadece takipli", variable=self.var_rb_takipli, bg="white").pack(side="left", padx=(10, 0))
        tk.Checkbutton(top, text="Sadece telefonu olanlar", variable=self.var_rb_telefonlu, bg="white").pack(side="left", padx=(6, 0))

        tk.Button(
            top, text="🔄 Listele", command=self._rapor_bitis_yukle,
            bg="#1976D2", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="left", padx=10)

        self.lbl_rb_sayac = tk.Label(top, text="", bg="white", fg="#455A64")
        self.lbl_rb_sayac.pack(side="left", padx=8)

        # Ana bölmesi: sol hasta listesi, sağ detay + mesaj
        bol = tk.PanedWindow(f, orient="horizontal", sashrelief="raised", bg="white")
        bol.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        sol = tk.Frame(bol, bg="white")
        bol.add(sol, minsize=430)

        kols = ("hasta", "tc", "tel", "tani_sayi", "en_yakin", "kalan", "takip")
        self.tv_rb = ttk.Treeview(sol, columns=kols, show="headings", selectmode="browse")
        for k, b, w, a in [
            ("hasta", "Hasta", 190, "w"),
            ("tc", "T.C.", 95, "center"),
            ("tel", "Telefon", 95, "center"),
            ("tani_sayi", "Tanı", 45, "center"),
            ("en_yakin", "En Yakın Bitiş", 100, "center"),
            ("kalan", "Kalan", 55, "center"),
            ("takip", "Takipli", 55, "center"),
        ]:
            self.tv_rb.heading(k, text=b)
            self.tv_rb.column(k, width=w, anchor=a)
        self.tv_rb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(sol, orient="vertical", command=self.tv_rb.yview)
        self.tv_rb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_rb.bind("<<TreeviewSelect>>", lambda e: self._rapor_bitis_detay())

        # Sağ: üstte detay tabloları, altta mesaj önizleme + WA gönder
        sag = tk.Frame(bol, bg="#FAFAFA")
        bol.add(sag, minsize=680)

        self.lbl_rb_hasta = tk.Label(
            sag, text="◀ Soldan bir hasta seçin",
            bg="#FAFAFA", fg="#607D8B",
            font=("Arial", 11, "bold"), anchor="w",
        )
        self.lbl_rb_hasta.pack(fill="x", padx=10, pady=(8, 4))

        # Tanı tablosu
        tk.Label(
            sag, text="Tanı / ICD / Bitiş Tarihleri", bg="#FAFAFA",
            fg="#1976D2", font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(4, 2))
        self.tv_rb_tani = ttk.Treeview(
            sag, columns=("kod", "aciklama", "icd", "icd_ad", "bas", "bit", "kalan"),
            show="headings", height=6,
        )
        for k, b, w in [
            ("kod", "Kod", 70), ("aciklama", "Tanı Açıklama", 200),
            ("icd", "ICD", 70), ("icd_ad", "ICD Açıklama", 200),
            ("bas", "Başlama", 90), ("bit", "Bitiş", 90), ("kalan", "Kalan", 55),
        ]:
            self.tv_rb_tani.heading(k, text=b)
            self.tv_rb_tani.column(k, width=w)
        self.tv_rb_tani.pack(fill="x", padx=10)

        # Etken maddeler + İlaçlar (yan yana)
        alt = tk.Frame(sag, bg="#FAFAFA")
        alt.pack(fill="x", padx=10, pady=(6, 0))

        em_frame = tk.Frame(alt, bg="#FAFAFA")
        em_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tk.Label(em_frame, text="Etken Maddeler", bg="#FAFAFA", fg="#1976D2", font=("Arial", 10, "bold")).pack(anchor="w")
        self.tv_rb_em = ttk.Treeview(em_frame, columns=("em", "sgk", "doz"), show="headings", height=4)
        self.tv_rb_em.heading("em", text="Etken Madde")
        self.tv_rb_em.heading("sgk", text="SGK")
        self.tv_rb_em.heading("doz", text="Doz")
        self.tv_rb_em.column("em", width=180)
        self.tv_rb_em.column("sgk", width=80, anchor="center")
        self.tv_rb_em.column("doz", width=60, anchor="center")
        self.tv_rb_em.pack(fill="both", expand=True)

        il_frame = tk.Frame(alt, bg="#FAFAFA")
        il_frame.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Label(il_frame, text="Kullanılan İlaçlar", bg="#FAFAFA", fg="#1976D2", font=("Arial", 10, "bold")).pack(anchor="w")
        self.tv_rb_il = ttk.Treeview(il_frame, columns=("ilac", "bitis", "tarih"), show="headings", height=4)
        self.tv_rb_il.heading("ilac", text="İlaç")
        self.tv_rb_il.heading("bitis", text="Bitiş")
        self.tv_rb_il.heading("tarih", text="Reçete Tarihi")
        self.tv_rb_il.column("ilac", width=220)
        self.tv_rb_il.column("bitis", width=80, anchor="center")
        self.tv_rb_il.column("tarih", width=90, anchor="center")
        self.tv_rb_il.pack(fill="both", expand=True)

        # Mesaj önizleme
        tk.Label(sag, text="Mesaj Önizleme", bg="#FAFAFA", fg="#1976D2", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.txt_rb_mesaj = tk.Text(sag, wrap="word", font=("Consolas", 9), height=6, bg="white", relief="solid", bd=1)
        self.txt_rb_mesaj.pack(fill="x", padx=10)

        btn_frame = tk.Frame(sag, bg="#FAFAFA")
        btn_frame.pack(fill="x", padx=10, pady=8)
        tk.Button(
            btn_frame, text="📱 WhatsApp Web'de Aç", command=self._rb_wa_ac,
            bg="#25D366", fg="white", bd=0, padx=16, pady=8, font=("Arial", 10, "bold"),
        ).pack(side="left")
        tk.Button(
            btn_frame, text="📋 Panoya Kopyala", command=self._rb_panoya,
            bg="#546E7A", fg="white", bd=0, padx=12, pady=8,
        ).pack(side="left", padx=8)

        self._rb_sonuc: list = []     # ham tanı satırları
        self._rb_hasta_map: dict = {} # musteri_id -> tanı satırları
        return f

    # ================================================================= SEKME LOG
    ISARET_SECENEK = ["", "✅ Gönderildi", "📞 Yanıt Geldi", "🧍 Geldi", "❌ Gelmedi", "🔁 Tekrar Dene"]

    def _sekme_log_olustur(self) -> tk.Frame:
        f = tk.Frame(self.notebook, bg="white")
        top = tk.Frame(f, bg="white")
        top.pack(fill="x", padx=10, pady=8)

        tk.Button(
            top, text="🔄 Yenile", command=self._log_yukle,
            bg="#1976D2", fg="white", bd=0, padx=14, pady=6,
        ).pack(side="left")
        tk.Label(
            top, text="Sağ tıkla → işaret / not düş",
            bg="white", fg="#607D8B", font=("Arial", 9, "italic"),
        ).pack(side="left", padx=12)

        kols = ("zaman", "hasta", "tel", "isaret", "not", "sonuc")
        self.tv_log = ttk.Treeview(
            f, columns=kols, show="headings", selectmode="browse",
        )
        for k, b, w in [
            ("zaman", "Zaman", 150),
            ("hasta", "Hasta", 220),
            ("tel", "Telefon", 110),
            ("isaret", "İşaret", 140),
            ("not", "Not", 240),
            ("sonuc", "Sonuç", 80),
        ]:
            self.tv_log.heading(k, text=b)
            self.tv_log.column(k, width=w, anchor="w")
        self.tv_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Sağ tık menüsü
        self.menu_log = tk.Menu(self.tv_log, tearoff=0)
        for isaret in self.ISARET_SECENEK:
            etiket = f"  İşaret: {isaret}" if isaret else "  İşareti Temizle"
            self.menu_log.add_command(
                label=etiket,
                command=lambda i=isaret: self._log_isaret(i),
            )
        self.menu_log.add_separator()
        self.menu_log.add_command(label="📝 Not Düş / Düzenle...", command=self._log_not)
        self.tv_log.bind("<Button-3>", self._log_sagtik)
        self.tv_log.bind("<Double-1>", lambda e: self._log_not())
        return f

    # -----------------------------------------------------------------
    # Sekme 1 davranışları
    # -----------------------------------------------------------------
    def _yazdirma_yenile(self):
        """DB'yi sorgula → kuyruğa upsert → ekrandaki listeyi güncelle."""
        self.durum_bar.config(text="DB sorgulanıyor...")
        self.root.update_idletasks()

        def _calis():
            try:
                if self.db is None:
                    self.db = HastaTakipDB()
                # Güncel ayarları çek (kaydedilmemiş olsa bile radio'dan)
                a = self._ayarlar_snapshot()
                sonuc = self.db.yazdirma_gunu_gelen_ilaclar(
                    tolerans_gun=a.hafta_sonu_tolerans_gun,
                    rapor_tolerans_gun=a.rapor_yazdirma_tolerans_gun,
                    sadece_takipli=a.sadece_takipli,
                    eski_kayit_gun=a.eski_kayit_gun,
                    kaynak=a.kaynak,
                )
                yeni = self.kuyruk.hasta_mesajlarini_upsert(sonuc, a)
                self.root.after(0, lambda: self._yazdirma_tamam(len(sonuc), yeni))
            except Exception as e:
                logger.exception("yazdirma_yenile hatası")
                self.root.after(0, lambda: messagebox.showerror("Hata", str(e)))

        threading.Thread(target=_calis, daemon=True).start()

    def _yazdirma_tamam(self, ilac_sayi: int, yeni_hasta: int):
        self._kuyruktan_yukle()
        gosterilen = len(self._kuyruk_sonuclari)
        self.durum_bar.config(
            text=f"✅ DB tarandı: {ilac_sayi} ilaç | {yeni_hasta} yeni hasta kuyruğa eklendi | "
                 f"Ekranda gösterilen: {gosterilen}",
        )
        if gosterilen == 0 and ilac_sayi > 0:
            messagebox.showinfo(
                "Liste Boş Görünüyor",
                f"Veritabanından {ilac_sayi} ilaç eşleşti ve kuyruğa yazıldı,\n"
                f"ancak ekranda gösterilmiyor.\n\n"
                f"Nedeni büyük ihtimalle ÇALIŞMA SAATİ ayarınızdır:\n"
                f"   {self.ayarlar.calisma_baslangic} - {self.ayarlar.calisma_bitis}\n\n"
                f"Ayarlar sekmesinden çalışma saatlerini genişletip 'Kaydet' yapın,\n"
                f"sonra yeniden 'Listeyi Yenile' deyin."
            )

    def _kuyruktan_yukle(self):
        for i in self.tv_yaz.get_children():
            self.tv_yaz.delete(i)
        a = self._ayarlar_snapshot()
        self._kuyruk_sonuclari = self.kuyruk.gosterilecek_mesajlar(a)
        for m in self._kuyruk_sonuclari:
            self.tv_yaz.insert(
                "", "end", iid=str(m["kuyruk_id"]),
                values=(
                    m["hasta_adi"],
                    m.get("tckn") or "-",
                    m["cep_tel"] or "-",
                    len(m["ilaclar"]),
                    m.get("toplam_ziyaret") if m.get("toplam_ziyaret") is not None else "-",
                    (m.get("son_ziyaret") or "")[:10] or "-",
                    m.get("son_gun_once") if m.get("son_gun_once") is not None else "-",
                    "Evet" if m.get("takipli") else "Hayır",
                    (m["planli_gonderim"] or "")[:10],
                ),
            )
        bekleyen = self.kuyruk.kuyrukta_bekleyen_sayisi()
        gosterilen = len(self._kuyruk_sonuclari)
        self.lbl_sayac.config(
            text=f"Kuyruktaki gösterilecek: {gosterilen}   |   "
                 f"Toplam bekleyen: {bekleyen}",
        )
        self.txt_mesaj.delete("1.0", "end")

        # Kullanıcıya neden boş olduğunu açıkla
        if gosterilen == 0 and bekleyen > 0:
            simdi = datetime.now().strftime("%H:%M")
            self.txt_mesaj.insert(
                "1.0",
                f"⚠ Kuyrukta {bekleyen} bekleyen kayıt var ama liste boş görünüyor.\n\n"
                f"OLASI NEDENLER:\n\n"
                f"1) ÇALIŞMA SAATİ DIŞINDASINIZ\n"
                f"   Şu an: {simdi}\n"
                f"   Ayarlar: {self.ayarlar.calisma_baslangic} - {self.ayarlar.calisma_bitis}\n"
                f"   → Ayarlar sekmesinden saatleri değiştirip 'Kaydet'e basın\n"
                f"     (ör. 00:00 - 23:59 yaparsanız her zaman görünür)\n\n"
                f"2) PLANLI GÖNDERİM İLERİDE\n"
                f"   Eğer 'Pazartesi birleşik' veya 'Periyodik' modundaysanız,\n"
                f"   kayıtlar o güne planlanmış olabilir.\n"
                f"   → Ayarlar sekmesinde 'Anlık' moduna geçin.",
            )
        elif gosterilen == 0 and bekleyen == 0:
            self.txt_mesaj.insert(
                "1.0",
                "Kuyrukta hiç kayıt yok.\n\n"
                "➤ Yukarıdaki '🔄 Listeyi Yenile (DB)' butonuna basarak\n"
                "  Botanik veritabanını tarayın."
            )

    def _secim_guncelle(self):
        sec = self.tv_yaz.selection()
        if not sec:
            return
        kid = int(sec[0])
        m = next((x for x in self._kuyruk_sonuclari if x["kuyruk_id"] == kid), None)
        if not m:
            return
        self.txt_mesaj.delete("1.0", "end")
        self.txt_mesaj.insert("1.0", m["mesaj_metni"])

    def _aktif_mesaj(self):
        sec = self.tv_yaz.selection()
        if not sec:
            messagebox.showwarning("Seçim Yok", "Lütfen bir hasta seçin.")
            return None
        kid = int(sec[0])
        return next((x for x in self._kuyruk_sonuclari if x["kuyruk_id"] == kid), None)

    def _wa_ac(self):
        m = self._aktif_mesaj()
        if not m:
            return
        tel = (m["cep_tel"] or "").strip()
        if not tel or len(tel) < 10:
            messagebox.showwarning("Telefon Yok", f"{m['hasta_adi']} için cep telefonu tanımlı değil.")
            return
        if tel.startswith("+"):
            tel = tel[1:]
        if tel.startswith("0"):
            tel = "90" + tel[1:]
        if not tel.startswith("90"):
            tel = "90" + tel

        mesaj_metni = self.txt_mesaj.get("1.0", "end").rstrip("\n")
        url = f"https://wa.me/{tel}?text={urllib.parse.quote(mesaj_metni)}"
        webbrowser.open(url)
        self.kuyruk.gonderildi_isaretle(m["kuyruk_id"], "OK")
        self._kuyruktan_yukle()
        self.durum_bar.config(text=f"✅ {m['hasta_adi']} için WhatsApp açıldı, kuyruktan düşürüldü.")

    def _panoya_kopyala(self):
        mesaj = self.txt_mesaj.get("1.0", "end").rstrip("\n")
        if not mesaj:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(mesaj)
        self.durum_bar.config(text="📋 Mesaj panoya kopyalandı.")

    def _kopyala_yardimci(self, alan: str, etiket: str):
        m = self._aktif_mesaj()
        if not m:
            return
        deger = (m.get(alan) or "").strip()
        if not deger:
            self.durum_bar.config(text=f"⚠ {etiket} yok.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(deger)
        self.durum_bar.config(text=f"📋 {etiket} panoya kopyalandı: {deger}")

    def _tc_kopyala(self, *_):
        self._kopyala_yardimci("tckn", "T.C. Kimlik No")

    def _tel_kopyala(self, *_):
        self._kopyala_yardimci("cep_tel", "Telefon")

    def _ad_kopyala(self, *_):
        self._kopyala_yardimci("hasta_adi", "Hasta adı")

    def _yaz_sagtik(self, event):
        rid = self.tv_yaz.identify_row(event.y)
        if not rid:
            return
        self.tv_yaz.selection_set(rid)
        try:
            self.menu_yaz.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_yaz.grab_release()

    def _secilene_gonder(self):
        """Seçilen tek hasta için wa.me aç — _wa_ac ile aynı."""
        self._wa_ac()

    def _secili_iptal(self):
        m = self._aktif_mesaj()
        if not m:
            return
        if not messagebox.askyesno("Onay", f"{m['hasta_adi']} iptal edilsin mi?"):
            return
        self.kuyruk.iptal_et(m["kuyruk_id"])
        self._kuyruktan_yukle()
        self.durum_bar.config(text=f"❌ {m['hasta_adi']} iptal edildi.")

    # -----------------------------------------------------------------
    # Sekme 2/3 davranışları
    # -----------------------------------------------------------------
    @staticmethod
    def _tarih_parse(s: str) -> "Optional[date]":
        s = (s or "").strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _int_parse(s: str):
        s = (s or "").strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None

    def _portfoy_yukle(self):
        bas = self._tarih_parse(self.var_pf_bas.get())
        bit = self._tarih_parse(self.var_pf_bit.get())
        son = self._tarih_parse(self.var_pf_songelis.get())
        if self.var_pf_songelis.get().strip() and son is None:
            messagebox.showwarning("Geçersiz Tarih", "Son geliş tarihini YYYY-AA-GG biçiminde girin.")
            return
        if (bas and not bit) or (bit and not bas):
            messagebox.showwarning("Geçersiz Aralık", "Başlangıç ve bitiş tarihini birlikte girin.")
            return

        self.durum_bar.config(text="Hasta portföyü yükleniyor...")
        self.root.update_idletasks()
        try:
            if self.db is None:
                self.db = HastaTakipDB()
            sonuc = self.db.hasta_portfoyu_getir(
                baslangic=bas, bitis=bit,
                sadece_telefonlu=bool(self.var_pf_tel.get()),
                son_gelis_sonra=son,
                sadece_takipli=bool(self.var_pf_takip.get()),
                min_ziyaret=self._int_parse(self.var_pf_min.get()),
                max_ziyaret=self._int_parse(self.var_pf_max.get()),
            )
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        self._portfoy_sonuc = {}  # musteri_id -> row (detay için)
        for i in self.tv_portfoy.get_children():
            self.tv_portfoy.delete(i)
        for r in sonuc[:10000]:
            mid = r.get("musteri_id")
            self._portfoy_sonuc[str(mid)] = r
            self.tv_portfoy.insert("", "end", iid=str(mid), values=(
                r.get("hasta_adi") or "",
                r.get("cep_tel") or "",
                r.get("ziyaret_sayisi"),
                r.get("recete_sayisi"),
                r.get("ilk_ziyaret") or "",
                r.get("son_ziyaret") or "",
                r.get("son_ziyaretten_gun"),
                "Evet" if r.get("takipli") else "Hayır",
            ))
        self.lbl_portfoy.config(
            text=f"Toplam: {len(sonuc)} hasta (ilk {min(len(sonuc), 10000)} gösteriliyor)"
        )
        self.durum_bar.config(text="Portföy yüklendi.")

    def _portfoy_hasta_detay(self):
        """Seçilen hastanın detay notebook'unu doldur."""
        sec = self.tv_portfoy.selection()
        if not sec:
            return
        mid = int(sec[0])
        r = self._portfoy_sonuc.get(str(mid), {})
        self.lbl_pf_detay.config(
            text=f"🧑 {r.get('hasta_adi','')}  |  📞 {r.get('cep_tel','-')}  |  "
                 f"ziyaret: {r.get('ziyaret_sayisi')}  |  son: {r.get('son_ziyaret','-')}"
        )

        if self.db is None:
            self.db = HastaTakipDB()

        # Raporlar
        for w in self.tv_pf_rap.get_children():
            self.tv_pf_rap.delete(w)
        try:
            raporlar = self.db.hastanin_aktif_raporlari(mid)
            for x in raporlar:
                self.tv_pf_rap.insert("", "end", values=(
                    x.get("rapor_no") or "", x.get("rapor_turu") or "",
                    x.get("rapor_tarihi") or "", x.get("bitis_tarihi") or "",
                    x.get("bitise_kac_gun") if x.get("bitise_kac_gun") is not None else "",
                    x.get("hastane") or "",
                ))
        except Exception as e:
            logger.warning("raporlar yüklenemedi: %s", e)

        # Yaklaşan yazdırmalar
        for w in self.tv_pf_yaz.get_children():
            self.tv_pf_yaz.delete(w)
        try:
            yazdirmalar = self.db.hastanin_yaklasan_yazdirmalari(
                mid, geri_gun=60, ileri_gun=30,
                rapor_tolerans_gun=self.ayarlar.rapor_yazdirma_tolerans_gun,
            )
            for x in yazdirmalar:
                self.tv_pf_yaz.insert("", "end", values=(
                    (x.get("urun_adi") or "")[:60],
                    x.get("bitis_tarihi") or "",
                    x.get("yazdirma_tarihi") or "",
                    x.get("kac_gun_kaldi") if x.get("kac_gun_kaldi") is not None else "",
                    x.get("rapor_no") or "",
                ))
        except Exception as e:
            logger.warning("yazdirmalar yüklenemedi: %s", e)

        # İlaç geçmişi
        for w in self.tv_pf_il.get_children():
            self.tv_pf_il.delete(w)
        try:
            ilaclar = self.db.hastanin_ilac_gecmisi(mid, limit=500)
            for x in ilaclar:
                self.tv_pf_il.insert("", "end", values=(
                    x.get("recete_tarihi") or "",
                    (x.get("urun_adi") or "")[:60],
                    x.get("adet"),
                    x.get("bitis_tarihi") or "",
                    x.get("rapor_no") or "",
                ))
        except Exception as e:
            logger.warning("ilac gecmisi yüklenemedi: %s", e)

    def _devamlilik_yukle(self):
        self.durum_bar.config(text="Devamlılık raporu yükleniyor...")
        self.root.update_idletasks()
        try:
            if self.db is None:
                self.db = HastaTakipDB()
            sonuc = self.db.devamlilik_raporu()
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return
        for i in self.tv_devam.get_children():
            self.tv_devam.delete(i)
        for r in sonuc[:5000]:  # 90bin satır için UI don mamalı — top 5000
            self.tv_devam.insert("", "end", values=(
                r.get("hasta_adi") or "",
                r.get("cep_tel") or "",
                r.get("dogum_tarihi") or "",
                r.get("recete_adedi"),
                r.get("son_recete_tarihi") or "",
                r.get("kac_gun_oldu"),
                "Evet" if r.get("takipli") else "Hayır",
            ))
        self.lbl_devam.config(text=f"Toplam: {len(sonuc)} hasta (ilk 5000 gösteriliyor)")
        self.durum_bar.config(text="Devamlılık raporu yüklendi.")

    # -----------------------------------------------------------------
    # Rapor Bitiş Takibi davranışları
    # -----------------------------------------------------------------
    def _rapor_bitis_yukle(self):
        try:
            if self.db is None:
                self.db = HastaTakipDB()
            sonuc = self.db.yaklasan_rapor_bitisleri(
                uyari_gun=int(self.var_rb_gun.get()),
                sadece_takipli=bool(self.var_rb_takipli.get()),
                sadece_telefonlu=bool(self.var_rb_telefonlu.get()),
                eski_gun=int(self.var_rb_geri.get()),
            )
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        self._rb_sonuc = sonuc
        # Hasta bazında grupla
        gruplu: dict = {}
        for r in sonuc:
            gruplu.setdefault(r["musteri_id"], []).append(r)
        self._rb_hasta_map = gruplu

        for i in self.tv_rb.get_children():
            self.tv_rb.delete(i)

        for mid, satirlar in gruplu.items():
            ilk = satirlar[0]
            en_yakin = min((str(s.get("bitis") or "") for s in satirlar if s.get("bitis")), default="")
            en_yakin_kalan = min((s.get("kalan_gun") for s in satirlar if s.get("kalan_gun") is not None), default="")
            self.tv_rb.insert("", "end", iid=str(mid), values=(
                ilk.get("hasta_adi") or "",
                ilk.get("tckn") or "-",
                ilk.get("cep_tel") or "-",
                len(satirlar),
                (en_yakin or "")[:10],
                en_yakin_kalan,
                "Evet" if ilk.get("takipli") else "Hayır",
            ))

        self.lbl_rb_sayac.config(
            text=f"Toplam: {len(gruplu)} hasta | {len(sonuc)} tanı satırı"
        )
        self.durum_bar.config(text=f"Rapor bitiş taraması tamam: {len(gruplu)} hasta")

    def _rapor_bitis_detay(self):
        sec = self.tv_rb.selection()
        if not sec:
            return
        mid = int(sec[0])
        satirlar = self._rb_hasta_map.get(mid, [])
        if not satirlar:
            return

        ilk = satirlar[0]
        self.lbl_rb_hasta.config(
            text=f"🧑 {ilk.get('hasta_adi','')}  |  📞 {ilk.get('cep_tel','-')}  |  "
                 f"T.C. {ilk.get('tckn','-')}  |  {len(satirlar)} tanı satırı"
        )

        # Tanı tablosu
        for w in self.tv_rb_tani.get_children():
            self.tv_rb_tani.delete(w)
        for t in satirlar:
            self.tv_rb_tani.insert("", "end", values=(
                t.get("rapor_kodu") or "",
                (t.get("rapor_kod_aciklama") or "").strip()[:50],
                t.get("icd_kodu") or "",
                (t.get("icd_aciklamasi") or "").strip()[:50],
                str(t.get("baslama") or "")[:10],
                str(t.get("bitis") or "")[:10],
                t.get("kalan_gun") if t.get("kalan_gun") is not None else "",
            ))

        # Etken madde ve ilaç — tüm rapor_id'ler için birleştir
        rapor_ids = list({t.get("rapor_id") for t in satirlar if t.get("rapor_id")})
        em_map: dict = {}
        il_map: dict = {}
        tum_em = []
        tum_il = []
        for rid in rapor_ids:
            try:
                d = self.db.raporun_detayi(rid, mid)
            except Exception:
                d = {"etkin_maddeler": [], "ilaclar": []}
            em_map[rid] = d.get("etkin_maddeler") or []
            il_map[rid] = d.get("ilaclar") or []
            tum_em.extend(em_map[rid])
            tum_il.extend(il_map[rid])

        for w in self.tv_rb_em.get_children():
            self.tv_rb_em.delete(w)
        gorulen_em = set()
        for em in tum_em:
            k = (em.get("etkin_madde"), em.get("sgk_kodu"))
            if k in gorulen_em:
                continue
            gorulen_em.add(k)
            self.tv_rb_em.insert("", "end", values=(
                em.get("etkin_madde") or "",
                em.get("sgk_kodu") or "",
                em.get("doz") or "",
            ))

        for w in self.tv_rb_il.get_children():
            self.tv_rb_il.delete(w)
        gorulen_il = set()
        for il in tum_il:
            ad = il.get("urun_adi") or ""
            if ad in gorulen_il:
                continue
            gorulen_il.add(ad)
            self.tv_rb_il.insert("", "end", values=(
                ad[:60],
                str(il.get("bitis_tarihi") or "")[:10],
                str(il.get("recete_tarihi") or "")[:10],
            ))

        # Mesaj önizleme
        mesaj = self.kuyruk.rapor_bitis_mesaji_olustur(
            ilk.get("hasta_adi") or "", satirlar, em_map, il_map, self.ayarlar,
        )
        self.txt_rb_mesaj.delete("1.0", "end")
        self.txt_rb_mesaj.insert("1.0", mesaj)

    def _rb_aktif_hasta(self):
        sec = self.tv_rb.selection()
        if not sec:
            messagebox.showwarning("Seçim Yok", "Bir hasta seçin.")
            return None, None
        mid = int(sec[0])
        satirlar = self._rb_hasta_map.get(mid, [])
        return mid, satirlar[0] if satirlar else None

    def _rb_wa_ac(self):
        mid, ilk = self._rb_aktif_hasta()
        if not ilk:
            return
        tel = (ilk.get("cep_tel") or "").strip()
        if not tel or len(tel) < 10:
            messagebox.showwarning("Telefon Yok", f"{ilk.get('hasta_adi')} için telefon tanımlı değil.")
            return
        if tel.startswith("+"):
            tel = tel[1:]
        if tel.startswith("0"):
            tel = "90" + tel[1:]
        if not tel.startswith("90"):
            tel = "90" + tel
        mesaj = self.txt_rb_mesaj.get("1.0", "end").rstrip("\n")
        if not mesaj:
            return
        url = f"https://wa.me/{tel}?text={urllib.parse.quote(mesaj)}"
        webbrowser.open(url)
        # Log'a yaz
        with self.kuyruk._conn() as c:
            c.execute(
                "INSERT INTO gonderim_log(musteri_id, hasta_adi, cep_tel, mesaj_metni, zaman, sonuc, isaret) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, ilk.get("hasta_adi"), tel, mesaj,
                 datetime.now().isoformat(timespec="seconds"), "OK", "📑 Rapor Bitiş"),
            )
        self.durum_bar.config(text=f"✅ {ilk.get('hasta_adi')} için rapor bitiş mesajı WhatsApp Web'de açıldı.")

    def _rb_panoya(self):
        mesaj = self.txt_rb_mesaj.get("1.0", "end").rstrip("\n")
        if not mesaj:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(mesaj)
        self.durum_bar.config(text="📋 Rapor bitiş mesajı panoya kopyalandı.")

    # -----------------------------------------------------------------
    # Sekme 4 — Ayarları kaydet
    # -----------------------------------------------------------------
    def _ayarlar_snapshot(self) -> HastaTakipAyarlari:
        """Ekrandaki form değerlerinden anlık ayar nesnesi üret."""
        a = HastaTakipAyarlari.yukle()
        a.gonderim_modu = self.var_mod.get()
        a.periyot_gun = int(self.var_periyot.get())
        a.hafta_sonu_tolerans_gun = int(self.var_hs.get())
        a.rapor_yazdirma_tolerans_gun = int(self.var_rt.get())
        a.eski_kayit_gun = int(self.var_eski.get())
        a.sadece_takipli = bool(self.var_takipli.get())
        a.kaynak = self.var_kaynak.get()
        a.calisma_baslangic = self.var_bas.get()
        a.calisma_bitis = self.var_bit.get()
        a.eczane_adi = self.var_ec_ad.get()
        a.eczane_tel = self.var_ec_tel.get()
        a.mesaj_sablonu = self.txt_sablon.get("1.0", "end").rstrip("\n")
        a.ilac_satir_formati = self.var_satir.get()
        a.toplu_gonderim_gunu = int(self.var_gonderim_gun.get())
        # Rapor bitiş şablonları
        if hasattr(self, "var_rb_uyari"):
            a.rapor_bitis_uyari_gun = int(self.var_rb_uyari.get())
        if hasattr(self, "txt_rb_sablon"):
            a.rapor_bitis_mesaj_sablonu = self.txt_rb_sablon.get("1.0", "end").rstrip("\n")
        if hasattr(self, "txt_rb_tani_sablon"):
            a.rapor_bitis_tani_satir_formati = self.txt_rb_tani_sablon.get("1.0", "end").rstrip("\n")
        return a

    def _ayarlari_kaydet(self):
        a = self._ayarlar_snapshot()
        a.kaydet()
        self.ayarlar = a
        messagebox.showinfo("Kaydedildi", "Ayarlar kaydedildi.")
        self.durum_bar.config(text="Ayarlar kaydedildi.")

    # -----------------------------------------------------------------
    # Sekme 5 — log
    # -----------------------------------------------------------------
    def _log_yukle(self):
        for i in self.tv_log.get_children():
            self.tv_log.delete(i)
        for r in self.kuyruk.log_getir():
            self.tv_log.insert("", "end", iid=str(r["id"]), values=(
                r.get("zaman"), r.get("hasta_adi"), r.get("cep_tel"),
                r.get("isaret") or "",
                (r.get("not_metni") or "")[:80],
                r.get("sonuc") or "",
            ))

    def _log_sagtik(self, event):
        rid = self.tv_log.identify_row(event.y)
        if not rid:
            return
        self.tv_log.selection_set(rid)
        try:
            self.menu_log.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_log.grab_release()

    def _log_secili_id(self) -> "Optional[int]":
        sec = self.tv_log.selection()
        if not sec:
            messagebox.showwarning("Seçim Yok", "Bir satır seçin.")
            return None
        return int(sec[0])

    def _log_isaret(self, isaret: str):
        lid = self._log_secili_id()
        if lid is None:
            return
        self.kuyruk.log_isaret_guncelle(lid, isaret)
        self._log_yukle()
        self.durum_bar.config(text=f"İşaret güncellendi: {isaret or '(temiz)'}")

    def _log_not(self):
        from tkinter import simpledialog
        lid = self._log_secili_id()
        if lid is None:
            return
        # Mevcut notu getir
        mevcut = ""
        for r in self.kuyruk.log_getir(limit=1000):
            if r["id"] == lid:
                mevcut = r.get("not_metni") or ""
                break
        yeni = simpledialog.askstring(
            "Not Düş", "Bu mesaj için not:", initialvalue=mevcut, parent=self.root,
        )
        if yeni is None:
            return
        self.kuyruk.log_not_guncelle(lid, yeni)
        self._log_yukle()
        self.durum_bar.config(text="Not güncellendi.")

    # -----------------------------------------------------------------
    def _kapat(self):
        try:
            if self.db:
                self.db.kapat()
        except Exception:
            pass
        if self.ana_menu_callback:
            self.root.destroy()
            self.ana_menu_callback()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    HastaTakipGUI(root)
    root.mainloop()
