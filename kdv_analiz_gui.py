"""
KDV Analiz GUI
Aylık bazda KDV beyanı için tahmini hesap arayüzü.
Motor: kdv_analiz_motoru.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
from datetime import date

from kdv_analiz_motoru import kdv_analiz_yap, KDVAnalizSonucu, OranOzeti

logger = logging.getLogger(__name__)

AY_ADLARI = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]

RENK_BAZ = "#37474F"
RENK_BAS = "#1A237E"
RENK_BG = "#ECEFF1"
RENK_PNL = "#F5F5F5"
RENK_VURGU = "#1565C0"
RENK_UYARI = "#C62828"
RENK_OK = "#2E7D32"


def fmt_tl(deger: float) -> str:
    if deger is None:
        return "—"
    isaret = "-" if deger < 0 else ""
    deger = abs(deger)
    return f"{isaret}{deger:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(deger: int) -> str:
    return f"{int(deger):,}".replace(",", ".")


class KDVAnalizGUI:
    def __init__(self, parent, ana_menu_callback=None):
        self.parent = parent
        self.ana_menu_callback = ana_menu_callback

        self.parent.title("KDV Analiz - Aylık Tahmini Beyan")
        self.parent.geometry("1400x850")
        self.parent.configure(bg=RENK_BG)

        bugun = date.today()
        oncekiay = bugun.month - 1 or 12
        oncekiyil = bugun.year if bugun.month > 1 else bugun.year - 1
        self.yil_var = tk.IntVar(value=oncekiyil)
        self.ay_var = tk.IntVar(value=oncekiay)

        self.son_sonuc: KDVAnalizSonucu | None = None

        self._arayuz_olustur()

    # ---------- ARAYÜZ ----------
    def _arayuz_olustur(self):
        header = tk.Frame(self.parent, bg=RENK_BAS, height=54)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="💰 KDV Analiz — Aylık Tahmini Beyan",
                 bg=RENK_BAS, fg="white",
                 font=("Arial", 15, "bold")).pack(pady=14)

        main = tk.Frame(self.parent, bg=RENK_BG, padx=12, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        self._param_panel(main)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.tab_ozet = tk.Frame(self.notebook, bg=RENK_PNL)
        self.tab_oran = tk.Frame(self.notebook, bg=RENK_PNL)
        self.tab_satis = tk.Frame(self.notebook, bg=RENK_PNL)
        self.tab_fis = tk.Frame(self.notebook, bg=RENK_PNL)

        self.notebook.add(self.tab_ozet, text="📊 Özet")
        self.notebook.add(self.tab_oran, text="📐 Oran Dağılımı")
        self.notebook.add(self.tab_satis, text="🧾 Satış Detayı")
        self.notebook.add(self.tab_fis, text="🔍 Fiş Kontrol")

        self._ozet_paneli_kur()
        self._oran_paneli_kur()
        self._satis_paneli_kur()
        self._fis_paneli_kur()

        self.status = tk.Label(main, text="Lütfen ay seçip 'Hesapla' butonuna basın.",
                               bg=RENK_BG, fg=RENK_BAZ, font=("Arial", 9, "italic"),
                               anchor="w")
        self.status.pack(fill=tk.X, pady=(6, 0))

    def _param_panel(self, parent):
        frame = tk.LabelFrame(parent, text="  Dönem Seçimi  ",
                              font=("Arial", 10, "bold"),
                              bg="#FFF3E0", padx=12, pady=10)
        frame.pack(fill=tk.X)

        tk.Label(frame, text="Yıl:", bg="#FFF3E0",
                 font=("Arial", 10)).pack(side=tk.LEFT)
        bugun = date.today()
        yillar = [bugun.year, bugun.year - 1, bugun.year - 2, bugun.year - 3]
        self.yil_combo = ttk.Combobox(frame, textvariable=self.yil_var,
                                      values=yillar, width=6, state="readonly")
        self.yil_combo.pack(side=tk.LEFT, padx=(4, 14))

        tk.Label(frame, text="Ay:", bg="#FFF3E0",
                 font=("Arial", 10)).pack(side=tk.LEFT)
        ay_secenekleri = ["★ Tüm Yıl"] + [f"{i+1:02d} - {AY_ADLARI[i]}" for i in range(12)]
        self.ay_combo = ttk.Combobox(frame,
                                     values=ay_secenekleri,
                                     width=18, state="readonly")
        # Combobox index: 0 = Tüm Yıl, 1..12 = aylar
        self.ay_combo.current(self.ay_var.get())  # default: önceki ay
        self.ay_combo.pack(side=tk.LEFT, padx=(4, 20))

        self.btn_hesapla = tk.Button(frame, text="🔍  Hesapla",
                                     font=("Arial", 11, "bold"),
                                     bg=RENK_VURGU, fg="white",
                                     padx=18, pady=6,
                                     command=self._hesapla_baslat,
                                     activebackground="#0D47A1",
                                     activeforeground="white",
                                     cursor="hand2")
        self.btn_hesapla.pack(side=tk.LEFT)

        bilgi = tk.Label(frame,
                         text=" KDV beyan dönemi: her ayın 26'sına kadar bir önceki ay beyan edilir.",
                         bg="#FFF3E0", fg=RENK_BAZ,
                         font=("Arial", 9, "italic"))
        bilgi.pack(side=tk.LEFT, padx=(20, 0))

    # ---------- ÖZET ----------
    def _ozet_paneli_kur(self):
        kart_frame = tk.Frame(self.tab_ozet, bg=RENK_PNL, padx=20, pady=20)
        kart_frame.pack(fill=tk.BOTH, expand=True)

        for i in range(2):
            kart_frame.columnconfigure(i, weight=1, uniform="kart")
        for i in range(4):
            kart_frame.rowconfigure(i, weight=1, uniform="kart_row")

        self.ozet_kartlari = {}
        kartlar = [
            ("toplam_satis", "Toplam Satış (KDV Dahil)", "#1565C0", 0, 0),
            ("toplam_matrah", "Toplam Satış Matrahı", "#0277BD", 0, 1),
            ("hesap_kdv", "Hesaplanan KDV (Satış)", "#F57C00", 1, 0),
            ("indir_kdv", "İndirilecek KDV (Alış)", "#388E3C", 1, 1),
            ("odenecek", "ÖDENECEK KDV (Tahmini)", "#C62828", 2, 0),
            ("alim_tutar", "Toplam Alım (KDV Hariç)", "#5D4037", 2, 1),
            ("fis_kesilmemis", "Fiş Kesilmemiş Elden Satış", "#AD1457", 3, 0),
            ("pos_toplam", "POS Tahsilat Toplamı", "#283593", 3, 1),
        ]
        for key, etiket, renk, r, c in kartlar:
            kart = tk.Frame(kart_frame, bg=renk, padx=20, pady=16,
                            relief="raised", bd=1)
            kart.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            tk.Label(kart, text=etiket, bg=renk, fg="white",
                     font=("Arial", 10, "bold")).pack(anchor="w")
            deger_lbl = tk.Label(kart, text="—", bg=renk, fg="white",
                                 font=("Arial", 18, "bold"))
            deger_lbl.pack(anchor="e", pady=(6, 0))
            ek_lbl = tk.Label(kart, text="", bg=renk, fg="white",
                              font=("Arial", 9, "italic"))
            ek_lbl.pack(anchor="e")
            self.ozet_kartlari[key] = (deger_lbl, ek_lbl)

    # ---------- ORAN ----------
    def _oran_paneli_kur(self):
        ust = tk.Label(self.tab_oran,
                       text="KDV oranlarına göre satış matrahı ve hesaplanan KDV dağılımı",
                       bg=RENK_PNL, fg=RENK_BAZ, font=("Arial", 11, "bold"))
        ust.pack(anchor="w", padx=14, pady=(14, 8))

        cols = ("Oran", "Matrah", "KDV", "Tutar(KDV Dahil)", "Satır Adet", "Pay (%)")
        self.oran_tree = ttk.Treeview(self.tab_oran, columns=cols,
                                      show="headings", height=10)
        for c in cols:
            self.oran_tree.heading(c, text=c)
        self.oran_tree.column("Oran", width=80, anchor="center")
        self.oran_tree.column("Matrah", width=180, anchor="e")
        self.oran_tree.column("KDV", width=160, anchor="e")
        self.oran_tree.column("Tutar(KDV Dahil)", width=180, anchor="e")
        self.oran_tree.column("Satır Adet", width=120, anchor="center")
        self.oran_tree.column("Pay (%)", width=100, anchor="center")
        self.oran_tree.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

        self.oran_tree.tag_configure("toplam", background="#FFE0B2",
                                     font=("Arial", 10, "bold"))

        alt = tk.Label(self.tab_oran,
                       text="ALIM matrah/KDV dağılımı (KDV indirimi tabanı)",
                       bg=RENK_PNL, fg=RENK_BAZ, font=("Arial", 11, "bold"))
        alt.pack(anchor="w", padx=14, pady=(4, 8))

        cols_a = ("Oran", "Matrah (KDV Hariç)", "İndirilecek KDV", "Satır Adet")
        self.alim_tree = ttk.Treeview(self.tab_oran, columns=cols_a,
                                      show="headings", height=6)
        for c in cols_a:
            self.alim_tree.heading(c, text=c)
        self.alim_tree.column("Oran", width=80, anchor="center")
        self.alim_tree.column("Matrah (KDV Hariç)", width=200, anchor="e")
        self.alim_tree.column("İndirilecek KDV", width=180, anchor="e")
        self.alim_tree.column("Satır Adet", width=120, anchor="center")
        self.alim_tree.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))
        self.alim_tree.tag_configure("toplam", background="#C8E6C9",
                                     font=("Arial", 10, "bold"))

    # ---------- SATIŞ DETAY ----------
    def _satis_paneli_kur(self):
        tk.Label(self.tab_satis,
                 text="Satış kaynağı bazında KDV oranı dağılımı",
                 bg=RENK_PNL, fg=RENK_BAZ,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 8))

        cols = ("Kaynak", "Oran", "Matrah", "KDV", "Tutar (KDV Dahil)", "Satır Adet")
        self.satis_tree = ttk.Treeview(self.tab_satis, columns=cols,
                                       show="headings", height=18)
        for c in cols:
            self.satis_tree.heading(c, text=c)
        self.satis_tree.column("Kaynak", width=140, anchor="w")
        self.satis_tree.column("Oran", width=80, anchor="center")
        self.satis_tree.column("Matrah", width=160, anchor="e")
        self.satis_tree.column("KDV", width=140, anchor="e")
        self.satis_tree.column("Tutar (KDV Dahil)", width=180, anchor="e")
        self.satis_tree.column("Satır Adet", width=100, anchor="center")
        self.satis_tree.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

        self.satis_tree.tag_configure("elden", background="#FFF9C4")
        self.satis_tree.tag_configure("recete", background="#E1F5FE")
        self.satis_tree.tag_configure("fatura", background="#F3E5F5")
        self.satis_tree.tag_configure("toplam", background="#FFCCBC",
                                      font=("Arial", 10, "bold"))

    # ---------- FİŞ KONTROL ----------
    def _fis_paneli_kur(self):
        ust = tk.Frame(self.tab_fis, bg=RENK_PNL, padx=14, pady=14)
        ust.pack(fill=tk.X)

        baslik = tk.Label(ust,
                          text="🔍 Fiş Kontrol — Perakende elden satışların fiş takibi",
                          bg=RENK_PNL, fg=RENK_BAZ,
                          font=("Arial", 12, "bold"))
        baslik.pack(anchor="w")

        aciklama = tk.Label(ust,
                            text=("Reçeteli ve kuruma kesilmiş satışlar fatura ile çıkar.\n"
                                  "POS ile alınan ödemelerin fişi yazar kasaya otomatik düşer.\n"
                                  "Bir 'EldenAna' kaydı KesilenFisTakibi tablosunda yer almıyorsa fiş kesilmemiştir.\n"
                                  "Bu satışlar büyük olasılıkla nakit perakende ve KDV ödenmemiş olabilir."),
                            bg=RENK_PNL, fg=RENK_BAZ,
                            font=("Arial", 9, "italic"), justify="left")
        aciklama.pack(anchor="w", pady=(4, 0))

        kart_frm = tk.Frame(self.tab_fis, bg=RENK_PNL, padx=14, pady=10)
        kart_frm.pack(fill=tk.X)

        self.kart_kesilmis = self._kart_yap(kart_frm, "Fiş Kesilmiş", RENK_OK)
        self.kart_kesilmemis = self._kart_yap(kart_frm, "Fiş Kesilmemiş", RENK_UYARI)
        self.kart_oran = self._kart_yap(kart_frm, "Kesilmeme Oranı", "#FFA000")

        tk.Label(self.tab_fis,
                 text="POS Tahsilat Dağılımı (Belge tipine göre)",
                 bg=RENK_PNL, fg=RENK_BAZ,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 6))

        cols = ("Belge Tipi", "İşlem Adedi", "Toplam Tutar")
        self.pos_tree = ttk.Treeview(self.tab_fis, columns=cols,
                                     show="headings", height=6)
        for c in cols:
            self.pos_tree.heading(c, text=c)
        self.pos_tree.column("Belge Tipi", width=180, anchor="w")
        self.pos_tree.column("İşlem Adedi", width=120, anchor="center")
        self.pos_tree.column("Toplam Tutar", width=180, anchor="e")
        self.pos_tree.pack(fill=tk.X, padx=14, pady=(0, 14))
        self.pos_tree.tag_configure("toplam", background="#FFE0B2",
                                    font=("Arial", 10, "bold"))

        self.kdvsiz_lbl = tk.Label(self.tab_fis, text="",
                                   bg=RENK_PNL, fg=RENK_BAZ,
                                   font=("Arial", 10), justify="left",
                                   wraplength=1200)
        self.kdvsiz_lbl.pack(anchor="w", padx=14, pady=(4, 14))

    def _kart_yap(self, parent, baslik, renk):
        kart = tk.Frame(parent, bg=renk, padx=20, pady=12, relief="raised", bd=1)
        kart.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        tk.Label(kart, text=baslik, bg=renk, fg="white",
                 font=("Arial", 10, "bold")).pack(anchor="w")
        deger = tk.Label(kart, text="—", bg=renk, fg="white",
                         font=("Arial", 18, "bold"))
        deger.pack(anchor="e", pady=(4, 0))
        ek = tk.Label(kart, text="", bg=renk, fg="white",
                      font=("Arial", 9, "italic"))
        ek.pack(anchor="e")
        return (deger, ek)

    # ---------- HESAPLAMA ----------
    def _hesapla_baslat(self):
        try:
            yil = int(self.yil_var.get())
            secim = self.ay_combo.current()  # 0 = Tüm Yıl, 1..12 = aylar
            ay = None if secim == 0 else secim
        except Exception:
            messagebox.showerror("Hata", "Yıl ve ay seçimini doğru yapın.")
            return

        donem = f"{yil} (tüm yıl)" if ay is None else f"{yil}-{ay:02d}"
        self.btn_hesapla.config(state="disabled", text="Hesaplanıyor...")
        self.status.config(text=f"{donem} dönemi hesaplanıyor...", fg=RENK_VURGU)

        def calistir():
            try:
                sonuc = kdv_analiz_yap(yil, ay)
                self.parent.after(0, self._sonucu_goster, sonuc)
            except Exception as e:
                logger.error("Hesaplama hatası: %s", e, exc_info=True)
                self.parent.after(0, self._hata_goster, str(e))

        threading.Thread(target=calistir, daemon=True).start()

    def _hata_goster(self, mesaj: str):
        self.btn_hesapla.config(state="normal", text="🔍  Hesapla")
        self.status.config(text=f"HATA: {mesaj}", fg=RENK_UYARI)
        messagebox.showerror("KDV Analiz Hatası", mesaj)

    def _sonucu_goster(self, sonuc: KDVAnalizSonucu):
        self.btn_hesapla.config(state="normal", text="🔍  Hesapla")
        if sonuc.hata:
            self._hata_goster(sonuc.hata)
            return
        self.son_sonuc = sonuc

        # Özet kartları
        self.ozet_kartlari["toplam_satis"][0].config(
            text=fmt_tl(sonuc.toplam_satis_tutar))
        self.ozet_kartlari["toplam_matrah"][0].config(
            text=fmt_tl(sonuc.toplam_satis_matrah))
        self.ozet_kartlari["hesap_kdv"][0].config(
            text=fmt_tl(sonuc.toplam_hesaplanan_kdv))
        self.ozet_kartlari["indir_kdv"][0].config(
            text=fmt_tl(sonuc.toplam_alim_kdv))
        self.ozet_kartlari["odenecek"][0].config(
            text=fmt_tl(sonuc.odenecek_kdv))
        self.ozet_kartlari["odenecek"][1].config(
            text=("Devreden KDV (alacak)" if sonuc.odenecek_kdv < 0
                  else "Devlete ödenecek"))
        self.ozet_kartlari["alim_tutar"][0].config(
            text=fmt_tl(sonuc.toplam_alim_tutar))
        self.ozet_kartlari["fis_kesilmemis"][0].config(
            text=fmt_tl(sonuc.fis_kesilmemis_tutar))
        self.ozet_kartlari["fis_kesilmemis"][1].config(
            text=f"{sonuc.fis_kesilmemis_adet} adet satış")
        pos_toplam = sum(d.get("tutar", 0) for d in sonuc.pos_dagilim.values())
        self.ozet_kartlari["pos_toplam"][0].config(text=fmt_tl(pos_toplam))

        # Oran tablosu
        for item in self.oran_tree.get_children():
            self.oran_tree.delete(item)
        toplam_matrah = sonuc.toplam_satis_matrah
        toplam_kdv_dahil = sonuc.toplam_satis_tutar
        matrahlar = sonuc.toplam_oran_matrahlari()
        kdvler = sonuc.toplam_oran_kdvleri()
        kdv_dahil_per_oran = {}
        for kaynak in (sonuc.elden, sonuc.recete, sonuc.fatura_cikis):
            for oran, ozet in kaynak.items():
                kdv_dahil_per_oran[oran] = kdv_dahil_per_oran.get(oran, 0) + ozet.tutar
        satir_per_oran = {}
        for kaynak in (sonuc.elden, sonuc.recete, sonuc.fatura_cikis):
            for oran, ozet in kaynak.items():
                satir_per_oran[oran] = satir_per_oran.get(oran, 0) + ozet.satir_adet
        for oran in sorted(matrahlar.keys()):
            m = matrahlar[oran]
            k = kdvler.get(oran, 0)
            t = kdv_dahil_per_oran.get(oran, 0)
            s = satir_per_oran.get(oran, 0)
            if m == 0 and k == 0:
                continue
            pay = (m / toplam_matrah * 100) if toplam_matrah else 0
            self.oran_tree.insert("", "end", values=(
                f"%{oran}", fmt_tl(m), fmt_tl(k), fmt_tl(t),
                fmt_int(s), f"{pay:.1f}%"))
        self.oran_tree.insert("", "end", values=(
            "TOPLAM", fmt_tl(toplam_matrah),
            fmt_tl(sonuc.toplam_hesaplanan_kdv),
            fmt_tl(toplam_kdv_dahil),
            fmt_int(sum(satir_per_oran.values())),
            "100.0%"), tags=("toplam",))

        # Alım tablosu
        for item in self.alim_tree.get_children():
            self.alim_tree.delete(item)
        for oran in sorted(sonuc.alim.keys()):
            o = sonuc.alim[oran]
            if o.tutar == 0:
                continue
            self.alim_tree.insert("", "end", values=(
                f"%{oran}", fmt_tl(o.matrah), fmt_tl(o.kdv),
                fmt_int(o.satir_adet)))
        self.alim_tree.insert("", "end", values=(
            "TOPLAM", fmt_tl(sonuc.toplam_alim_tutar),
            fmt_tl(sonuc.toplam_alim_kdv),
            fmt_int(sum(o.satir_adet for o in sonuc.alim.values()))),
            tags=("toplam",))

        # Satış detay
        for item in self.satis_tree.get_children():
            self.satis_tree.delete(item)
        for ad, grup, tag in (("ELDEN", sonuc.elden, "elden"),
                              ("REÇETE", sonuc.recete, "recete"),
                              ("FATURA ÇIKIŞ", sonuc.fatura_cikis, "fatura")):
            grup_toplam_m = grup_toplam_k = grup_toplam_t = grup_toplam_s = 0
            for oran in sorted(grup.keys()):
                o = grup[oran]
                if o.tutar == 0:
                    continue
                self.satis_tree.insert("", "end", values=(
                    ad, f"%{oran}", fmt_tl(o.matrah), fmt_tl(o.kdv),
                    fmt_tl(o.tutar), fmt_int(o.satir_adet)), tags=(tag,))
                grup_toplam_m += o.matrah
                grup_toplam_k += o.kdv
                grup_toplam_t += o.tutar
                grup_toplam_s += o.satir_adet
            if grup_toplam_t > 0:
                self.satis_tree.insert("", "end", values=(
                    f"{ad} TOPLAM", "—", fmt_tl(grup_toplam_m),
                    fmt_tl(grup_toplam_k), fmt_tl(grup_toplam_t),
                    fmt_int(grup_toplam_s)), tags=("toplam",))

        # Fiş analizi
        toplam_satis_adet = sonuc.fis_kesilmis_adet + sonuc.fis_kesilmemis_adet
        toplam_satis_tutar_elden = sonuc.fis_kesilmis_tutar + sonuc.fis_kesilmemis_tutar
        oran = (sonuc.fis_kesilmemis_tutar / toplam_satis_tutar_elden * 100) \
            if toplam_satis_tutar_elden else 0

        self.kart_kesilmis[0].config(text=fmt_tl(sonuc.fis_kesilmis_tutar))
        self.kart_kesilmis[1].config(text=f"{sonuc.fis_kesilmis_adet} satış")
        self.kart_kesilmemis[0].config(text=fmt_tl(sonuc.fis_kesilmemis_tutar))
        self.kart_kesilmemis[1].config(text=f"{sonuc.fis_kesilmemis_adet} satış")
        self.kart_oran[0].config(text=f"{oran:.1f}%")
        self.kart_oran[1].config(text="tutar bazlı")

        # POS dağılımı tablosu
        for item in self.pos_tree.get_children():
            self.pos_tree.delete(item)
        pos_top_adet = 0
        pos_top_tutar = 0.0
        for tip in sorted(sonuc.pos_dagilim.keys()):
            d = sonuc.pos_dagilim[tip]
            self.pos_tree.insert("", "end", values=(
                d["ad"], fmt_int(d["adet"]), fmt_tl(d["tutar"])))
            pos_top_adet += d["adet"]
            pos_top_tutar += d["tutar"]
        self.pos_tree.insert("", "end", values=(
            "TOPLAM", fmt_int(pos_top_adet), fmt_tl(pos_top_tutar)),
            tags=("toplam",))

        # KDV bilinmeyen ürün uyarısı
        uyari_satirlar = []
        if sonuc.elden_kdvsiz_satir_adet:
            uyari_satirlar.append(
                f"• Elden satışta KDV oranı bilinmeyen {sonuc.elden_kdvsiz_satir_adet} "
                f"satır var (toplam {fmt_tl(sonuc.elden_kdvsiz_tutar)}). "
                "Bu satırlar oran=0 grubuna eklendi.")
        if sonuc.recete_kdvsiz_satir_adet:
            uyari_satirlar.append(
                f"• Reçete satışında KDV oranı bilinmeyen {sonuc.recete_kdvsiz_satir_adet} "
                f"satır var (toplam {fmt_tl(sonuc.recete_kdvsiz_tutar)}). "
                "Bu satırlar oran=0 grubuna eklendi.")
        self.kdvsiz_lbl.config(
            text=("\n".join(uyari_satirlar) if uyari_satirlar
                  else "✓ Tüm satış satırlarında KDV oranı eşleşti."))

        donem_etiket = (f"{sonuc.yil} (tüm yıl)" if sonuc.ay is None
                        else f"{sonuc.yil}-{sonuc.ay:02d}")
        self.status.config(
            text=f"{donem_etiket} hesaplandı. "
                 f"Ödenecek KDV: {fmt_tl(sonuc.odenecek_kdv)}",
            fg=RENK_OK)


def main():
    """Modülü tek başına başlatmak için"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s")
    root = tk.Tk()
    KDVAnalizGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
