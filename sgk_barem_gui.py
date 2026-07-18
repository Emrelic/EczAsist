"""
SGK Barem / İskonto Etki Hesaplayıcı — GUI.

Eczanenin ciro yapısını (EOS'tan otomatik veya elle) alır; tek bir reçetenin
bu yılki kârını ve reçetenin hasılatı büyütmesi yüzünden gelecek yıl SGK'ya
yapılacak ekstra iskonto + hizmet bedeli kaybını gösterir.

Veri kaynağı: Botanik EOS (SADECE SELECT — botanik_db.BotanikDB üzerinden).
Kurallar: barem_kurallari.json (2026/1 Ek Protokol + Karar 11031).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import re
from datetime import date, datetime, timedelta

import sgk_barem_motoru as motor

logger = logging.getLogger(__name__)

BG = "#ECEFF1"
PANEL_BG = "#FFFFFF"
BASLIK_RENK = "#0D47A1"


def _tl(deger, ondalik=2) -> str:
    """Türkçe biçimde TL formatı: 1.234.567,89"""
    try:
        s = f"{float(deger):,.{ondalik}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "-"


def _sayi_oku(metin: str) -> float:
    """'12.000.000,50' / '600.000' / '12000000.5' girişlerini float'a çevir.

    Virgül = ondalık ayracı; virgül yoksa binlik desenindeki (X.XXX.XXX)
    noktalar binlik ayracı sayılır, aksi halde nokta ondalıktır.
    """
    s = (metin or "").strip().replace(" ", "").replace("TL", "")
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    return float(s)


def _yuzde(oran) -> str:
    """0.0105 → '%1,05'"""
    return f"%{oran * 100:.2f}".replace(".", ",")


class SGKBaremGUI:
    """SGK Barem / İskonto Etki Hesaplayıcı — bağımsız pencere."""

    def __init__(self, parent, ana_menu_callback=None):
        self.parent = parent
        self.ana_menu_callback = ana_menu_callback

        self.parent.title("SGK Barem / İskonto Etki Hesaplayıcı")
        self.parent.configure(bg=BG)

        try:
            self.kurallar = motor.kurallari_yukle()
        except Exception as e:
            logger.error(f"barem_kurallari.json okunamadı: {e}", exc_info=True)
            messagebox.showerror("Hata", f"barem_kurallari.json okunamadı:\n{e}")
            self.parent.destroy()
            return

        self.db = None  # EOS bağlantısı butona basılınca kurulur

        # --- Eczane profili değişkenleri ---
        self.aylik_ciro = tk.StringVar(value="")
        self.sgk_orani = tk.StringVar(value="70")           # %
        self.aylik_recete = tk.StringVar(value="")
        self.onceki_hasilat = tk.StringVar(value="")        # kesintiye esas yıl (Medula)
        self.barem_artis = tk.StringVar(value="40")         # gelecek barem artışı %
        self.muaf_sgk_orani = tk.StringVar(value="0")       # % (kan ürünü vb. payı)
        self.buyume_orani = tk.StringVar(value="0")         # %
        self.kdv_ayikla = tk.BooleanVar(value=True)
        self.kdv_orani = tk.StringVar(value="10")           # %
        bugun = date.today()
        self.donem_bas = tk.StringVar(
            value=(bugun - timedelta(days=365)).strftime("%d.%m.%Y"))
        self.donem_bit = tk.StringVar(value=bugun.strftime("%d.%m.%Y"))
        self.esas_yil = tk.StringVar(value=str(bugun.year - 2))
        yillar = sorted(self.kurallar.get("yillar", {}).keys())
        self.yil = tk.StringVar(value=str(self.kurallar.get("aktif_yil", yillar[-1])))

        # --- İstihdam (ikinci/yardımcı eczacı) maliyet değişkenleri ---
        self.fm_dahil = tk.BooleanVar(value=True)      # azami fazla mesai (270 saat/yıl)
        self.yemek_dahil = tk.BooleanVar(value=True)   # yasal yemek bedeli
        self.ikinci_maliyet = tk.StringVar(value="")
        self.yardimci_maliyet = tk.StringVar(value="")
        self._istihdam_maliyet_guncelle()

        # --- Reçete değişkenleri ---
        self.recete_tutar = tk.StringVar(value="")
        self.kar_tipi = tk.StringVar(value="alis")          # 'alis' | 'oran'
        self.recete_alis = tk.StringVar(value="")
        # Kâr/satış oranı varsayılanı: pahalı normal ilaçta kademeli kâr eğrisinin
        # yakınsadığı ~%11,5 (EOS ampirik doğrulaması %11,5-13). Kan ürününde %4'e çekilir.
        self.recete_kar_orani = tk.StringVar(value="11,5")  # %
        self.kan_urunu = tk.BooleanVar(value=False)
        self.mobil_soguk = tk.BooleanVar(value=False)
        self.aylik_tekrar = tk.BooleanVar(value=False)
        self.sirali_dagitim = tk.BooleanVar(value=False)
        varsayilan_oda = self.kurallar.get("oda_katki_payi_orani", 0.005) * 100
        self.oda_katki = tk.StringVar(value=f"{varsayilan_oda:g}".replace(".", ","))

        self._arayuz_olustur()
        self._pencereyi_icerige_sigdir()

    def _pencereyi_icerige_sigdir(self):
        """Pencereyi içeriğin istediği boyuta getir (ekran sınırları içinde)."""
        try:
            self.parent.update_idletasks()
            gerek_w = self.parent.winfo_reqwidth()
            gerek_h = self.parent.winfo_reqheight()
            ekran_w = self.parent.winfo_screenwidth()
            ekran_h = self.parent.winfo_screenheight()
            w = min(gerek_w + 16, ekran_w - 60)
            h = min(gerek_h + 16, ekran_h - 90)
            self.parent.geometry(f"{w}x{h}")
        except Exception:
            pass

    # ------------------------------------------------------------------ UI

    def _arayuz_olustur(self):
        header = tk.Frame(self.parent, bg=BASLIK_RENK)
        header.pack(fill="x")
        tk.Label(header, text="⚖️ SGK Barem / İskonto Etki Hesaplayıcı",
                 font=("Segoe UI", 16, "bold"), bg=BASLIK_RENK, fg="white",
                 pady=8).pack(side="left", padx=12)
        self.status_lbl = tk.Label(header, text="", font=("Segoe UI", 10),
                                   bg=BASLIK_RENK, fg="#BBDEFB")
        self.status_lbl.pack(side="right", padx=12)
        tk.Button(header, text="📈 Fiyat → Kârlılık", font=("Segoe UI", 10, "bold"),
                  bg="#0D47A1", fg="white", relief="raised",
                  command=self._fiyat_karlilik_ac).pack(side="right", padx=6, pady=6)

        govde = tk.Frame(self.parent, bg=BG)
        govde.pack(fill="both", expand=True, padx=10, pady=8)
        govde.columnconfigure(0, weight=0)
        govde.columnconfigure(1, weight=1)
        govde.rowconfigure(0, weight=1)

        sol = tk.Frame(govde, bg=BG)
        sol.grid(row=0, column=0, sticky="nsw")
        sag = tk.Frame(govde, bg=BG)
        sag.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        sag.rowconfigure(1, weight=1)
        sag.columnconfigure(0, weight=1)

        self._profil_paneli(sol)
        self._recete_paneli(sol)
        self._barem_tablosu_paneli(sag)
        self._sonuc_paneli(sag)

    def _panel(self, parent, baslik):
        cerceve = tk.LabelFrame(parent, text=baslik, bg=PANEL_BG,
                                font=("Segoe UI", 11, "bold"), fg=BASLIK_RENK,
                                padx=10, pady=8)
        cerceve.pack(fill="x", pady=(0, 8))
        return cerceve

    def _satir(self, parent, etiket, degisken, birim="", genislik=16):
        f = tk.Frame(parent, bg=PANEL_BG)
        f.pack(fill="x", pady=2)
        tk.Label(f, text=etiket, bg=PANEL_BG, font=("Segoe UI", 10),
                 width=30, anchor="w").pack(side="left")
        e = tk.Entry(f, textvariable=degisken, font=("Segoe UI", 10),
                     width=genislik, justify="right")
        e.pack(side="left")
        if birim:
            tk.Label(f, text=birim, bg=PANEL_BG,
                     font=("Segoe UI", 10)).pack(side="left", padx=(4, 0))
        return e

    def _profil_paneli(self, parent):
        p = self._panel(parent, "🏪 Eczane Profili")

        f_yil = tk.Frame(p, bg=PANEL_BG)
        f_yil.pack(fill="x", pady=2)
        tk.Label(f_yil, text="Barem yılı (kural seti)", bg=PANEL_BG,
                 font=("Segoe UI", 10), width=30, anchor="w").pack(side="left")
        cb = ttk.Combobox(f_yil, textvariable=self.yil, state="readonly", width=8,
                          values=sorted(self.kurallar.get("yillar", {}).keys()))
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self._barem_tablosu_doldur())

        self._satir(p, "Aylık ortalama TOPLAM ciro (KDV hariç)", self.aylik_ciro, "TL")
        self._satir(p, "SGK payı", self.sgk_orani, "%")
        self._satir(p, "Aylık SGK reçete sayısı", self.aylik_recete, "adet")
        self._satir(p, "SGK içinde iskonto MUAF pay (kan ürünü vb.)", self.muaf_sgk_orani, "%")
        self._satir(p, "Gelecek yıl ciro büyüme katsayısı", self.buyume_orani, "%")
        self._satir(p, "Kesintiye ESAS yıl hasılatı (Medula mesajı)", self.onceki_hasilat, "TL")
        self._satir(p, "Gelecek dönem barem ARTIŞ beklentisi", self.barem_artis, "%")
        tk.Label(p, text="Döngü: H yılı hasılatı → İTS beyanı ~7 Nis-6 May + SGK EK-5 → oran H+1'in 1 EKİM'inden geçerli\n"
                         "(geç ilanda retro ek fatura; 2026/1: Mart 2026 ilan → Ekim 2025). Bugünkü reçete 2026 hasılatına\n"
                         "girer → etkisi Ekim 2027+ kesintilerinde, o günün ARTIRILMIŞ baremleriyle (son artış +%60,7).",
                 bg=PANEL_BG, fg="#B71C1C", font=("Segoe UI", 8, "italic"),
                 justify="left").pack(anchor="w", pady=(2, 0))

        f_tarih = tk.Frame(p, bg=PANEL_BG)
        f_tarih.pack(fill="x", pady=(6, 0))
        tk.Label(f_tarih, text="EOS veri dönemi", bg=PANEL_BG,
                 font=("Segoe UI", 10), width=30, anchor="w").pack(side="left")
        tk.Entry(f_tarih, textvariable=self.donem_bas, width=11,
                 justify="center", font=("Segoe UI", 10)).pack(side="left")
        tk.Label(f_tarih, text="—", bg=PANEL_BG).pack(side="left", padx=2)
        tk.Entry(f_tarih, textvariable=self.donem_bit, width=11,
                 justify="center", font=("Segoe UI", 10)).pack(side="left")
        tk.Label(f_tarih, text="  Esas yıl:", bg=PANEL_BG,
                 font=("Segoe UI", 10)).pack(side="left")
        yil_simdi = date.today().year
        ttk.Combobox(f_tarih, textvariable=self.esas_yil, state="readonly", width=6,
                     values=[str(y) for y in range(yil_simdi - 5, yil_simdi + 1)]
                     ).pack(side="left", padx=(4, 0))

        f_eos = tk.Frame(p, bg=PANEL_BG)
        f_eos.pack(fill="x", pady=(4, 2))
        tk.Button(f_eos, text="📥 EOS'tan Doldur",
                  font=("Segoe UI", 10, "bold"), bg="#1565C0", fg="white",
                  command=self._eos_doldur).pack(side="left")
        tk.Checkbutton(f_eos, text="KDV ayıkla", variable=self.kdv_ayikla,
                       bg=PANEL_BG, font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        tk.Entry(f_eos, textvariable=self.kdv_orani, width=4,
                 justify="right").pack(side="left")
        tk.Label(f_eos, text="%   (dönem aylık ortalamaya çevrilir; esas yıl → Medula hasılatı)",
                 bg=PANEL_BG, font=("Segoe UI", 9), fg="#607D8B").pack(side="left")

        tk.Label(p, text="Barem TOPLAM hasılata göre (nakit dahil, KDV hariç); iskonto sadece SGK reçetelerine.",
                 bg=PANEL_BG, fg="#607D8B", font=("Segoe UI", 8, "italic"),
                 justify="left").pack(anchor="w", pady=(3, 0))

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=6)
        tk.Label(p, text="👨‍⚕️ İkinci / Yardımcı Eczacı İstihdamı", bg=PANEL_BG,
                 font=("Segoe UI", 10, "bold"), fg=BASLIK_RENK).pack(anchor="w")

        f_sec = tk.Frame(p, bg=PANEL_BG)
        f_sec.pack(fill="x", pady=1)
        tk.Checkbutton(f_sec, text="Azami fazla mesai dahil (270 saat/yıl, %50 zamlı)",
                       variable=self.fm_dahil, bg=PANEL_BG, font=("Segoe UI", 9),
                       command=self._istihdam_maliyet_guncelle).pack(anchor="w")
        tk.Checkbutton(f_sec, text="Yemek bedeli dahil (300 TL/gün × 26 gün)",
                       variable=self.yemek_dahil, bg=PANEL_BG, font=("Segoe UI", 9),
                       command=self._istihdam_maliyet_guncelle).pack(anchor="w")

        self._satir(p, "İkinci eczacı aylık TAM maliyeti", self.ikinci_maliyet, "TL")
        self._satir(p, "Yardımcı eczacı aylık TAM maliyeti", self.yardimci_maliyet, "TL")

        self.ist_detay_lbl = tk.Label(p, text="", bg=PANEL_BG, fg="#607D8B",
                                      font=("Segoe UI", 8, "italic"), justify="left")
        self.ist_detay_lbl.pack(anchor="w", pady=(2, 0))
        self._istihdam_detay_yaz()

    def _istihdam_maliyet_guncelle(self):
        """Yasal tabanlardan tam işveren maliyetini hesapla, alanlara yaz."""
        try:
            m = motor.istihdam_varsayilan_maliyetler(
                self.kurallar, fazla_mesai=self.fm_dahil.get(),
                yemek=self.yemek_dahil.get())
            self.ikinci_maliyet.set(_tl(m["ikinci"]["aylik_toplam"]))
            self.yardimci_maliyet.set(_tl(m["yardimci"]["aylik_toplam"]))
        except Exception as e:
            logger.warning(f"İstihdam maliyet hesabı yapılamadı: {e}")
        if hasattr(self, "ist_detay_lbl"):
            self._istihdam_detay_yaz()

    def _istihdam_detay_yaz(self):
        try:
            ist = motor.istihdam_konfig(self.kurallar)
            m = motor.istihdam_varsayilan_maliyetler(
                self.kurallar, fazla_mesai=self.fm_dahil.get(),
                yemek=self.yemek_dahil.get())
            i, y = m["ikinci"], m["yardimci"]
            metin = (
                f"Eşikler: ikinci {_tl(ist['ikinci_eczaci_hasilat_esigi'], 0)} TL veya "
                f"{ist['ikinci_eczaci_recete_esigi']:,} rç/yıl".replace(",", ".")
                + f" (her katta +1, azami {ist.get('azami_ikinci_eczaci', 3)}); "
                f"yardımcı {_tl(ist['yardimci_eczaci_hasilat_esigi'], 0)} TL.\n"
                f"İkinci: brüt {_tl(i['brut_ucret'], 0)} (3×asg) → {_tl(i['ucret_maliyeti'], 0)}"
                f" + FM {_tl(i['fazla_mesai_maliyeti'], 0)} + yemek {_tl(i['yemek_tutari'], 0)} | "
                f"Yardımcı: {_tl(y['brut_ucret'], 0)} (1,5×) → {_tl(y['ucret_maliyeti'], 0)}"
                f" + FM {_tl(y['fazla_mesai_maliyeti'], 0)} + yemek {_tl(y['yemek_tutari'], 0)}\n"
                f"(2026: asgari brüt 33.030; işveren çarpanı %{(i['isveren_carpani'] - 1) * 100:.2f}"
                .replace(".", ",") + " = SGK %21,75 + işsizlik %2 − teşvik 2 puan)")
        except Exception:
            metin = "İstihdam maliyet parametreleri barem_kurallari.json'da tanımlı değil."
        self.ist_detay_lbl.config(text=metin)

    def _recete_paneli(self, parent):
        p = self._panel(parent, "💊 Reçete Simülasyonu")

        self._satir(p, "Reçete tutarı (SGK'ya fatura)", self.recete_tutar, "TL")

        f1 = tk.Frame(p, bg=PANEL_BG)
        f1.pack(fill="x", pady=2)
        tk.Radiobutton(f1, text="Depo ödemesi (alış)", variable=self.kar_tipi,
                       value="alis", bg=PANEL_BG, font=("Segoe UI", 10),
                       width=26, anchor="w").pack(side="left")
        tk.Entry(f1, textvariable=self.recete_alis, width=16,
                 justify="right", font=("Segoe UI", 10)).pack(side="left")
        tk.Label(f1, text="TL", bg=PANEL_BG).pack(side="left", padx=(4, 0))

        f2 = tk.Frame(p, bg=PANEL_BG)
        f2.pack(fill="x", pady=2)
        tk.Radiobutton(f2, text="veya kârlılık oranı (kâr/satış)", variable=self.kar_tipi,
                       value="oran", bg=PANEL_BG, font=("Segoe UI", 10),
                       width=26, anchor="w").pack(side="left")
        tk.Entry(f2, textvariable=self.recete_kar_orani, width=16,
                 justify="right", font=("Segoe UI", 10)).pack(side="left")
        tk.Label(f2, text="% (pahalı ilaçta teorik ~%11,5 — bkz. 📈)", bg=PANEL_BG,
                 font=("Segoe UI", 9), fg="#607D8B").pack(side="left", padx=(4, 0))

        tk.Checkbutton(p, text="🩸 Kan ürünü / enzim (depocu fiyatlı → iskonto MUAF)",
                       variable=self.kan_urunu, bg=PANEL_BG,
                       font=("Segoe UI", 10),
                       command=self._kan_urunu_degisti).pack(anchor="w", pady=1)
        self.kan_urunu_lbl = tk.Label(
            p, text="", bg=PANEL_BG, fg="#B71C1C",
            font=("Segoe UI", 8, "italic"), justify="left")
        self.kan_urunu_lbl.pack(anchor="w")
        f_oda = tk.Frame(p, bg=PANEL_BG)
        f_oda.pack(fill="x", pady=1)
        tk.Checkbutton(f_oda, text="🏛️ Sıralı dağıtım (oda onaylı) — oda katkı payı",
                       variable=self.sirali_dagitim, bg=PANEL_BG,
                       font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(f_oda, textvariable=self.oda_katki, width=6,
                 justify="right", font=("Segoe UI", 10)).pack(side="left", padx=(6, 0))
        tk.Label(f_oda, text="% (İstanbul EO fiili: %1,2 = %1 + KDV — e-bandrol dökümünden doğrulandı)",
                 bg=PANEL_BG, font=("Segoe UI", 9), fg="#607D8B").pack(side="left", padx=(4, 0))
        tk.Checkbutton(p, text="🧊 Mobil / soğuk zincir reçete (hizmet bedeli %50 artırımlı)",
                       variable=self.mobil_soguk, bg=PANEL_BG,
                       font=("Segoe UI", 10)).pack(anchor="w", pady=1)
        tk.Checkbutton(p, text="🔁 Reçete her ay tekrarlanacak (12 ay boyunca)",
                       variable=self.aylik_tekrar, bg=PANEL_BG,
                       font=("Segoe UI", 10)).pack(anchor="w", pady=1)

        tk.Button(p, text="🧮 HESAPLA", font=("Segoe UI", 12, "bold"),
                  bg="#2E7D32", fg="white", pady=6,
                  command=self._hesapla).pack(fill="x", pady=(8, 2))

    def _kan_urunu_degisti(self):
        """Kan ürünü seçilince gerçekçi kârlılık bandını öner (araştırma bulgusu).

        Depocu fiyatlı ilaçlarda yasal eczacı kârı yok; kâr = depo iskontosu,
        piyasada tipik %2-7 (çoğunlukla %3-5). Normal ilaçta pahalı dilim ~%13.
        """
        if self.kan_urunu.get():
            self.kan_urunu_lbl.config(
                text="Yasal kâr YOK — kâr = depo iskontosu (tipik %2-7); oran %4'e çekildi, kendi iskontonu girebilirsin.")
            if self.recete_kar_orani.get().strip() in ("11,5", "7", "13"):
                self.recete_kar_orani.set("4")
            self.sirali_dagitim.set(True)  # kan ürünü/enzim daima sıralı dağıtımda
        else:
            self.kan_urunu_lbl.config(text="")
            if self.recete_kar_orani.get().strip() == "4":
                self.recete_kar_orani.set("11,5")

    def _barem_tablosu_paneli(self, parent):
        cerceve = tk.LabelFrame(parent, text="📐 Eşik Haritası — bugünkü değerler; işaretler GELECEK dönem (artış beklentili) kıyasa göre",
                                bg=PANEL_BG, font=("Segoe UI", 11, "bold"),
                                fg=BASLIK_RENK, padx=6, pady=4)
        cerceve.grid(row=0, column=0, sticky="ew")

        kolonlar = ("dilim", "aralik", "iskonto", "hizmet", "durum")
        self.barem_tablo = ttk.Treeview(cerceve, columns=kolonlar, show="headings",
                                        height=10)
        basliklar = {"dilim": ("Dilim", 50), "aralik": ("Hasılat aralığı (TL)", 300),
                     "iskonto": ("İskonto", 80), "hizmet": ("Hizmet bedeli", 110),
                     "durum": ("Durum", 260)}
        for k, (b, w) in basliklar.items():
            self.barem_tablo.heading(k, text=b)
            self.barem_tablo.column(k, width=w, anchor="center" if k != "aralik" else "w")
        self.barem_tablo.pack(fill="x")
        self.barem_tablo.tag_configure("mevcut", background="#C8E6C9")
        self.barem_tablo.tag_configure("yeni", background="#FFCDD2")
        self.barem_tablo.tag_configure("istihdam", background="#E1F5FE")
        self.barem_tablo.tag_configure("istihdam_asildi", background="#FFE0B2")
        self.barem_tablo.tag_configure("istihdam_yeni", background="#FFCDD2")
        self._barem_tablosu_doldur()

    def _sonuc_paneli(self, parent):
        cerceve = tk.LabelFrame(parent, text="📊 Sonuç", bg=PANEL_BG,
                                font=("Segoe UI", 11, "bold"), fg=BASLIK_RENK,
                                padx=6, pady=4)
        cerceve.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        cerceve.rowconfigure(0, weight=1)
        cerceve.columnconfigure(0, weight=1)

        self.sonuc_txt = tk.Text(cerceve, font=("Consolas", 10), wrap="word",
                                 bg="#FAFAFA", state="disabled",
                                 width=88, height=16)
        scroll = ttk.Scrollbar(cerceve, command=self.sonuc_txt.yview)
        self.sonuc_txt.configure(yscrollcommand=scroll.set)
        self.sonuc_txt.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        for tag, renk, kalin in (("baslik", BASLIK_RENK, True),
                                 ("pozitif", "#2E7D32", True),
                                 ("negatif", "#C62828", True),
                                 ("uyari", "#E65100", True),
                                 ("gri", "#607D8B", False)):
            self.sonuc_txt.tag_configure(
                tag, foreground=renk,
                font=("Consolas", 10, "bold") if kalin else ("Consolas", 10))

    # ------------------------------------------------------------- yardımcı

    def _status(self, mesaj, hata=False):
        self.status_lbl.config(text=mesaj, fg="#FFCDD2" if hata else "#BBDEFB")

    def _cfg(self):
        return motor.yil_konfig(self.kurallar, self.yil.get())

    def _barem_tablosu_doldur(self, mevcut_idx=None, yeni_idx=None,
                              hasilat_once=None, hasilat_sonra=None,
                              esik_carpani=1.0):
        """Eşik haritasını doldur: iskonto dilimleri + istihdam eşikleri.

        hasilat_once/hasilat_sonra verilirse istihdam eşiklerinde aşım durumu
        (mevcut projeksiyonla ve reçete sonrası) işaretlenir.
        """
        self.barem_tablo.delete(*self.barem_tablo.get_children())
        cfg = self._cfg()
        isk = cfg["iskonto_baremleri"]
        hb = cfg["hizmet_bedeli_baremleri"]
        alt = 0.0
        for i, dilim in enumerate(isk):
            ust = dilim.get("ust")
            aralik = (f"{_tl(alt, 0)} — {_tl(ust, 0)}" if ust is not None
                      else f"{_tl(alt, 0)} üzeri")
            # Aynı hasılat noktasındaki hizmet bedelini bul (dilim ortası temsilci)
            temsilci = (alt + ust) / 2 if ust is not None else alt * 1.1 + 1
            h_idx = motor._dilim_bul(hb, temsilci)
            durum, tag = "", ""
            if mevcut_idx is not None and i == mevcut_idx and i == (yeni_idx if yeni_idx is not None else mevcut_idx):
                durum, tag = "◄ MEVCUT (reçete sonrası da burada)", "mevcut"
            elif mevcut_idx is not None and i == mevcut_idx:
                durum, tag = "◄ MEVCUT", "mevcut"
            elif yeni_idx is not None and i == yeni_idx:
                durum, tag = "◄◄ REÇETE SONRASI (BAREM ATLADI!)", "yeni"
            self.barem_tablo.insert(
                "", "end",
                values=(i + 1, aralik, f"%{dilim['oran'] * 100:.2f}".replace(".", ","),
                        _tl(hb[h_idx]["tutar"]) + " TL", durum),
                tags=(tag,) if tag else ())
            alt = ust if ust is not None else alt

        # İstihdam eşikleri (yardımcı + ikinci eczacı katları)
        try:
            ist = motor.istihdam_konfig(self.kurallar)
        except Exception:
            return

        def _istihdam_satir(ad, esik):
            esik_c = esik * esik_carpani  # gelecek dönem eşiği (artış beklentili)
            durum, tag = "", "istihdam"
            if hasilat_once is not None:
                sonra = hasilat_sonra if hasilat_sonra is not None else hasilat_once
                if hasilat_once > esik_c:
                    durum, tag = "AŞILMIŞ — yükümlülük zaten var", "istihdam_asildi"
                elif sonra > esik_c:
                    durum, tag = "◄◄ REÇETE SONRASI AŞILIYOR!", "istihdam_yeni"
                else:
                    durum = f"kalan: {_tl(esik_c - sonra, 0)} TL"
                if esik_carpani != 1.0:
                    ad = f"{ad} (gelecek ~{_tl(esik_c, 0)})"
            self.barem_tablo.insert(
                "", "end", values=("👨‍⚕️", ad, "—", "—", durum), tags=(tag,))

        _istihdam_satir(f"Yardımcı eczacı eşiği: {_tl(ist['yardimci_eczaci_hasilat_esigi'], 0)} TL",
                        ist["yardimci_eczaci_hasilat_esigi"])
        azami = ist.get("azami_ikinci_eczaci", 3)
        for kat in range(1, azami + 1):
            esik = ist["ikinci_eczaci_hasilat_esigi"] * kat
            _istihdam_satir(f"{kat}. ikinci eczacı eşiği: {_tl(esik, 0)} TL", esik)

    # ------------------------------------------------------------- EOS

    @staticmethod
    def _tarih_oku(metin: str) -> date:
        """'17.07.2026' / '2026-07-17' girişini date'e çevir."""
        s = (metin or "").strip()
        for kalip in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, kalip).date()
            except ValueError:
                continue
        raise ValueError(f"Tarih anlaşılamadı: '{metin}' (GG.AA.YYYY bekleniyor)")

    def _eos_doldur(self):
        """Seçilen dönemin SGK/nakit cirosunu + esas yıl hasılatını EOS'tan çek."""
        try:
            baslangic = self._tarih_oku(self.donem_bas.get())
            bitis = self._tarih_oku(self.donem_bit.get())
            esas_yil = int(self.esas_yil.get())
        except ValueError as e:
            messagebox.showwarning("Tarih hatası", str(e))
            return
        if baslangic >= bitis:
            messagebox.showwarning("Tarih hatası", "Dönem başlangıcı bitişten önce olmalı.")
            return
        ay_sayisi = max(1.0, (bitis - baslangic).days / 30.4375)
        self._status(f"EOS'tan {baslangic:%d.%m.%Y} — {bitis:%d.%m.%Y} "
                     f"({ay_sayisi:.1f} ay) + {esas_yil} yılı çekiliyor...")

        def _calis():
            try:
                if self.db is None:
                    from botanik_db import BotanikDB
                    db = BotanikDB()
                    if not db.baglan():
                        raise RuntimeError("Botanik EOS bağlantısı kurulamadı")
                    self.db = db
                satirlar = self.db.satis_raporu_getir(
                    baslangic, bitis, kirilim="tumu", periyot="aylik")
                recete_tl = sum(r["ReceteliTL"] for r in satirlar)
                elden_tl = sum(r["EldenTL"] for r in satirlar)
                recete_adet = sum(r["ReceteliSayisi"] for r in satirlar)
                esas_satirlar = self.db.satis_raporu_getir(
                    date(esas_yil, 1, 1), date(esas_yil, 12, 31),
                    kirilim="tumu", periyot="yillik")
                esas_toplam = sum(r["TLTutar"] for r in esas_satirlar)
                self.parent.after(
                    0, lambda: self._eos_sonuc(recete_tl, elden_tl, recete_adet,
                                               esas_yil, esas_toplam, ay_sayisi))
            except Exception as e:
                logger.error(f"EOS ciro çekme hatası: {e}", exc_info=True)
                self.parent.after(
                    0, lambda h=str(e): self._status(f"EOS hatası: {h}", hata=True))

        threading.Thread(target=_calis, daemon=True).start()

    def _eos_sonuc(self, recete_tl, elden_tl, recete_adet,
                   esas_yil=None, esas_toplam=0.0, ay_sayisi=12.0):
        if self.kdv_ayikla.get():
            try:
                kdv = _sayi_oku(self.kdv_orani.get()) / 100.0
            except ValueError:
                kdv = 0.10
            recete_tl /= (1.0 + kdv)
            elden_tl /= (1.0 + kdv)
            esas_toplam /= (1.0 + kdv)
        toplam = recete_tl + elden_tl
        if toplam <= 0:
            self._status("EOS'tan seçilen dönemde satış verisi gelmedi", hata=True)
            return
        self.aylik_ciro.set(_tl(toplam / ay_sayisi, 0))
        self.sgk_orani.set(f"{recete_tl / toplam * 100:.1f}".replace(".", ","))
        self.aylik_recete.set(str(round(recete_adet / ay_sayisi)))
        if esas_toplam > 0:
            self.onceki_hasilat.set(_tl(esas_toplam, 0))
        self._status(f"EOS: dönem toplamı {_tl(toplam, 0)} TL / {ay_sayisi:.1f} ay "
                     f"({recete_adet} rç); esas yıl {esas_yil}: {_tl(esas_toplam, 0)} TL "
                     f"{'(KDV ayıklandı)' if self.kdv_ayikla.get() else ''} — "
                     "Medula'daki resmî hasılatla karşılaştırın")

    # ------------------------------------------------------------- hesap

    def _hesapla(self):
        try:
            aylik_ciro = _sayi_oku(self.aylik_ciro.get())
            sgk_oran = _sayi_oku(self.sgk_orani.get()) / 100.0
            aylik_recete = _sayi_oku(self.aylik_recete.get())
            muaf_oran = _sayi_oku(self.muaf_sgk_orani.get()) / 100.0
            buyume = _sayi_oku(self.buyume_orani.get()) / 100.0
            tutar = _sayi_oku(self.recete_tutar.get())
        except ValueError as e:
            messagebox.showwarning("Giriş hatası", f"Sayısal alanları kontrol edin:\n{e}")
            return
        if aylik_ciro <= 0 or tutar <= 0:
            messagebox.showwarning(
                "Eksik giriş", "Aylık ciro ve reçete tutarı girilmeli.")
            return
        if not (0.0 <= sgk_oran <= 1.0):
            messagebox.showwarning("Giriş hatası", "SGK payı %0-100 arasında olmalı.")
            return

        alis = None
        kar_orani = None
        if self.kar_tipi.get() == "alis":
            try:
                alis = _sayi_oku(self.recete_alis.get())
            except ValueError:
                alis = 0.0
            if alis <= 0:
                messagebox.showwarning("Eksik giriş", "Depo ödemesi (alış) girilmeli "
                                       "veya kârlılık oranı seçilmeli.")
                return
        else:
            try:
                kar_orani = _sayi_oku(self.recete_kar_orani.get()) / 100.0
            except ValueError:
                kar_orani = 0.0

        try:
            cfg = self._cfg()
            sonuc = motor.tam_analiz(
                aylik_toplam_ciro=aylik_ciro,
                sgk_orani=sgk_oran,
                aylik_recete_sayisi=aylik_recete,
                recete_tutari=tutar,
                cfg=cfg,
                kurallar=self.kurallar,
                alis=alis,
                karlilik_orani=kar_orani,
                kan_urunu=self.kan_urunu.get(),
                mobil_soguk=self.mobil_soguk.get(),
                aylik_tekrar=self.aylik_tekrar.get(),
                iskonto_muaf_sgk_orani=muaf_oran,
                buyume_orani=buyume,
                aylik_ikinci_maliyet=_sayi_oku(self.ikinci_maliyet.get()),
                aylik_yardimci_maliyet=_sayi_oku(self.yardimci_maliyet.get()),
                oda_katki_orani=(_sayi_oku(self.oda_katki.get()) / 100.0
                                 if self.sirali_dagitim.get() else 0.0),
                onceki_yil_hasilat=(_sayi_oku(self.onceki_hasilat.get()) or None),
                barem_artis_orani=_sayi_oku(self.barem_artis.get()) / 100.0,
            )
        except Exception as e:
            logger.error(f"Barem hesap hatası: {e}", exc_info=True)
            messagebox.showerror("Hata", f"Hesaplama hatası:\n{e}")
            return

        self._barem_tablosu_doldur(
            mevcut_idx=sonuc["etki"]["onceki"]["iskonto_dilim"],
            yeni_idx=sonuc["etki"]["sonraki"]["iskonto_dilim"],
            hasilat_once=sonuc["yillik_hasilat"],
            hasilat_sonra=sonuc["yillik_hasilat"] + sonuc["ek_hasilat"],
            esik_carpani=sonuc.get("esik_carpani", 1.0))
        self._sonuc_yaz(sonuc)
        self._status("Hesaplandı ✓")

    def _sonuc_yaz(self, s):
        t = self.sonuc_txt
        t.config(state="normal")
        t.delete("1.0", "end")

        def yaz(metin, tag=None):
            t.insert("end", metin, (tag,) if tag else ())

        etki = s["etki"]
        kar = s["recete_kar"]
        mevcut = s["mevcut_barem"]
        tekrar = s.get("aylik_tekrar", False)

        carp = s.get("esik_carpani", 1.0)
        yaz("── ECZANE PROFİLİ ─────────────────────────────\n", "baslik")
        yaz(f"Bu yıl hasılat projeksiyonu        : {_tl(s['yillik_hasilat'])} TL "
            f"(SGK: {_tl(s['yillik_sgk_ciro'])} TL)\n")
        if s.get("onceki_yil_hasilat"):
            yaz(f"ŞU AN UYGULANAN kesinti            : esas yıl hasılatı "
                f"{_tl(s['onceki_yil_hasilat'])} TL → iskonto {_yuzde(mevcut['iskonto_orani'])}, "
                f"hizmet {_tl(mevcut['hizmet_bedeli'])} TL/rç (Medula mesajıyla karşılaştırın)\n")
        else:
            yaz(f"Mevcut kesinti (VARSAYIM)          : esas yıl girilmedi → bu yıl "
                f"projeksiyonundan: iskonto {_yuzde(mevcut['iskonto_orani'])}, "
                f"hizmet {_tl(mevcut['hizmet_bedeli'])} TL/rç\n", "uyari")
        if carp != 1.0:
            yaz(f"Gelecek dönem eşikleri             : bugünkü baremler × {carp:.2f} "
                f"(+{_yuzde(carp - 1.0)[1:]} artış beklentisi) ile kıyaslandı\n".replace(".", ","), "gri")
        onceki_b = etki["onceki"]
        if onceki_b["iskonto_bareme_kalan"] is not None:
            yaz(f"Bir üst iskonto eşiğine kalan      : {_tl(onceki_b['iskonto_bareme_kalan'])} TL "
                f"hasılat (gelecek dönem eşiğiyle)\n", "uyari")
        else:
            yaz("En üst iskonto baremindesiniz (gelecek dönem eşikleriyle).\n", "gri")
        if onceki_b["hizmet_bareme_kalan"] is not None:
            yaz(f"Bir alt hizmet bedeli dilimine kalan: {_tl(onceki_b['hizmet_bareme_kalan'])} TL hasılat\n", "gri")

        yaz("\n── REÇETENİN BU YILKİ KÂRI ────────────────────\n", "baslik")
        yaz(f"Brüt kâr (satış − alış)            : {_tl(kar['brut_kar'])} TL\n")
        if kar["iskonto_kesintisi"] > 0:
            yaz(f"SGK iskonto kesintisi (−)          : {_tl(kar['iskonto_kesintisi'])} TL "
                f"({_yuzde(mevcut['iskonto_orani'])})\n", "negatif")
        else:
            yaz("SGK iskonto kesintisi              : YOK (kan ürünü/enzim — iskonto muaf)\n", "pozitif")
        if kar.get("oda_katki_payi", 0) > 0:
            yaz(f"Oda katkı payı, sıralı dağıtım (−) : {_tl(kar['oda_katki_payi'])} TL\n", "negatif")
        yaz(f"Reçete başı hizmet bedeli (+)      : {_tl(kar['hizmet_bedeli'])} TL\n")
        yaz(f"NET KÂR (tek reçete)               : {_tl(kar['net_kar'])} TL\n",
            "pozitif" if kar["net_kar"] >= 0 else "negatif")
        if tekrar:
            yaz(f"Yıllık (12 tekrar) net kâr         : {_tl(s['recete_yillik_kar'])} TL\n", "pozitif")

        yaz("\n── GELECEK DÖNEM BAREM ETKİSİ (retro kesinti) ─\n", "baslik")
        yaz(f"Hasılata eklenen tutar             : {_tl(s['ek_hasilat'])} TL"
            f"{' (12 ay tekrar)' if tekrar else ''}\n")
        onceki, sonraki = etki["onceki"], etki["sonraki"]
        if etki["barem_atladi"] or etki["hizmet_dustu"]:
            if etki["barem_atladi"]:
                yaz(f"⚠ İSKONTO BAREMİ ATLIYOR: {onceki['iskonto_dilim'] + 1}. → "
                    f"{sonraki['iskonto_dilim'] + 1}. dilim "
                    f"({_yuzde(onceki['iskonto_orani'])} → {_yuzde(sonraki['iskonto_orani'])})\n",
                    "negatif")
                yaz(f"  Gelecek yıl ekstra iskonto       : {_tl(etki['ek_iskonto_maliyeti'])} TL "
                    f"(taban: {_tl(etki['gelecek_ciro'])} TL)\n", "negatif")
            if etki["hizmet_dustu"]:
                yaz(f"⚠ HİZMET BEDELİ DÜŞÜYOR: {_tl(onceki['hizmet_bedeli'])} → "
                    f"{_tl(sonraki['hizmet_bedeli'])} TL/reçete\n", "negatif")
                yaz(f"  Gelecek yıl hizmet bedeli kaybı  : {_tl(etki['hizmet_bedeli_kaybi'])} TL "
                    f"({etki['gelecek_recete_sayisi']:.0f} reçete)\n", "negatif")
            yaz(f"GELECEK YIL TOPLAM KAYIP           : {_tl(etki['toplam_gelecek_kayip'])} TL\n", "negatif")
        else:
            yaz("✓ Barem DEĞİŞMİYOR — bu reçete gelecek yıl iskonto/hizmet bedeline etki etmez.\n", "pozitif")

        ist = s.get("istihdam")
        if ist:
            yaz("\n── İKİNCİ / YARDIMCI ECZACI ETKİSİ ────────────\n", "baslik")
            o, n = ist["onceki"], ist["sonraki"]
            yaz(f"Mevcut yükümlülük                  : "
                f"{o['ikinci_sayisi']} ikinci eczacı, "
                f"yardımcı eczacı {'GEREKLİ' if o['yardimci_gerekli'] else 'gerekmiyor'}\n")
            if o["yardimci_esige_kalan"] is not None:
                yaz(f"Yardımcı eczacı eşiğine kalan      : {_tl(o['yardimci_esige_kalan'])} TL hasılat\n", "gri")
            if o["ikinci_esige_kalan"] is not None:
                yaz(f"Sonraki ikinci eczacı eşiğine kalan: {_tl(o['ikinci_esige_kalan'])} TL hasılat\n", "gri")
            if ist["ek_ikinci_eczaci"] > 0 or ist["yardimci_eklendi"]:
                if ist["ek_ikinci_eczaci"] > 0:
                    yaz(f"⚠ İKİNCİ ECZACI YÜKÜMLÜLÜĞÜ ARTIYOR: {o['ikinci_sayisi']} → "
                        f"{n['ikinci_sayisi']} kişi\n", "negatif")
                if ist["yardimci_eklendi"]:
                    yaz("⚠ YARDIMCI ECZACI YÜKÜMLÜLÜĞÜ DOĞUYOR\n", "negatif")
                yaz(f"Gelecek yıl ek istihdam maliyeti   : {_tl(ist['yillik_ek_maliyet'])} TL/yıl\n", "negatif")
            else:
                yaz("✓ Bu reçete istihdam yükümlülüğünü DEĞİŞTİRMİYOR.\n", "pozitif")

        yaz("\n── NET SONUÇ ──────────────────────────────────\n", "baslik")
        ist_maliyet = ist["yillik_ek_maliyet"] if ist else 0.0
        yaz(f"Reçete kârı{' (yıllık)' if tekrar else ''}                        : "
            f"{_tl(s['recete_yillik_kar'])} TL\n")
        yaz(f"Gelecek yıl barem kaybı (−)        : {_tl(etki['toplam_gelecek_kayip'])} TL\n")
        yaz(f"Gelecek yıl istihdam maliyeti (−)  : {_tl(ist_maliyet)} TL\n")
        yaz(f"NET SONUÇ                          : {_tl(s['net_sonuc'])} TL\n",
            "pozitif" if s["net_sonuc"] >= 0 else "negatif")
        if s["net_sonuc"] >= 0:
            yaz("→ Bu reçeteyi yapmak, barem + istihdam etkileri dahil edildiğinde de KÂRLI.\n", "pozitif")
        else:
            yaz("→ DİKKAT: Barem atlama / istihdam maliyeti reçete kârını aşıyor —\n"
                "  bu reçete (bu ciro yapısıyla) gelecek yıl kaybıyla birlikte ZARARDA.\n", "negatif")
        yaz("\nNot: Bu yıl hasılatı = aylık ciro × 12 projeksiyonu. Reçeteye BUGÜN kesilen\n"
            "iskonto/hizmet bedeli 'kesintiye esas yıl' hasılatından (Medula); reçetenin\n"
            "barem/istihdam etkisi ise GELECEK dönem eşikleriyle (bugünkü × artış beklentisi)\n"
            "hesaplanır — kesin sonuç, o baremler ilan edilince belli olur ve 1 Ekim'e retro\n"
            "uygulanır. Kurallar: barem_kurallari.json\n", "gri")

        t.config(state="disabled")

    # ---------------------------------------------------- fiyat→kârlılık

    def _fiyat_karlilik_ac(self):
        """İlaç fiyatı arttıkça eczacı kârlılığının nasıl düştüğünü gösteren tablo."""
        dilimler = self.kurallar.get("kademeli_kar", {}).get("dilimler")
        if not dilimler:
            messagebox.showwarning("Eksik", "kademeli_kar dilimleri JSON'da tanımlı değil.")
            return

        pencere = tk.Toplevel(self.parent)
        pencere.title("📈 İlaç Fiyatı → Eczacı Kârlılığı (Karar 11031, kademeli sistem)")
        pencere.geometry("860x560")
        pencere.configure(bg=BG)

        ust = tk.Frame(pencere, bg=BG)
        ust.pack(fill="x", padx=10, pady=6)
        tk.Label(ust, text="Depocu satış fiyatı (alış) girin:", bg=BG,
                 font=("Segoe UI", 10)).pack(side="left")
        ozel_dsf = tk.StringVar()
        tk.Entry(ust, textvariable=ozel_dsf, width=14,
                 justify="right").pack(side="left", padx=4)
        tk.Label(ust, text="TL", bg=BG).pack(side="left")

        kolonlar = ("dsf", "kar", "satis", "kar_alis", "kar_satis", "marjinal")
        tablo = ttk.Treeview(pencere, columns=kolonlar, show="headings", height=18)
        basliklar = {
            "dsf": ("Alış / DSF (TL)", 130), "kar": ("Eczacı kârı (TL)", 130),
            "satis": ("Satış KDV hariç (TL)", 150), "kar_alis": ("Kâr/Alış", 90),
            "kar_satis": ("Kâr/Satış", 90), "marjinal": ("Marjinal dilim", 110)}
        for k, (b, w) in basliklar.items():
            tablo.heading(k, text=b)
            tablo.column(k, width=w, anchor="e" if k != "marjinal" else "center")
        tablo.pack(fill="both", expand=True, padx=10, pady=4)
        tablo.tag_configure("esik", background="#FFF9C4")
        tablo.tag_configure("ozel", background="#B3E5FC")

        aciklama = tk.Label(
            pencere, bg=BG, fg="#607D8B", justify="left", font=("Segoe UI", 9),
            text="Kademeli sistem (gelir vergisi gibi): ilk 440,65 TL'ye %28, 440,65–882,66 arasına %18, "
                 "üstüne %13 kâr.\nFiyat arttıkça efektif kârlılık %28'den %13'e yakınsar — pahalı ilaç, "
                 "alış üzerinden daha az kâr bırakır.\nSarı satırlar dilim eşikleri; SGK satışında ayrıca "
                 "barem iskontosu ve reçete başı hizmet bedeli uygulanır (ana penceredeki hesap).\n"
                 "KKİ (kamu kurum iskontosu) TL kârı orantılı küçültür ama alış da aynı oranda küçüldüğü "
                 "için buradaki YÜZDELER geçerli kalır.\nEOS doğrulaması: en pahalı ürünlerde Botanik "
                 "eczane iskontosu ~%11,5-13 — teorik kâr/satış eğrisiyle örtüşüyor (2026-07 kontrolü).")
        aciklama.pack(anchor="w", padx=10, pady=(0, 8))

        varsayilan_dsf = [50, 100, 200, 300, 440.65, 600, 882.66, 1000, 1500,
                          2000, 3000, 5000, 10000, 25000, 50000, 100000]

        def doldur(ozel=None):
            tablo.delete(*tablo.get_children())
            dsf_list = list(varsayilan_dsf)
            if ozel and ozel > 0 and ozel not in dsf_list:
                dsf_list = sorted(dsf_list + [ozel])
            for r in motor.fiyat_karlilik_tablosu(dsf_list, dilimler):
                tag = ""
                if abs(r["dsf"] - 440.65) < 0.01 or abs(r["dsf"] - 882.66) < 0.01:
                    tag = "esik"
                if ozel and abs(r["dsf"] - ozel) < 0.005:
                    tag = "ozel"
                tablo.insert("", "end", values=(
                    _tl(r["dsf"]), _tl(r["kar"]), _tl(r["satis"]),
                    _yuzde(r["kar_alis_orani"]), _yuzde(r["kar_satis_orani"]),
                    _yuzde(r["marjinal_oran"])), tags=(tag,) if tag else ())

        def ozel_hesapla(*_a):
            try:
                deger = _sayi_oku(ozel_dsf.get())
            except ValueError:
                deger = 0.0
            doldur(deger if deger > 0 else None)

        tk.Button(ust, text="Hesapla", bg="#2E7D32", fg="white",
                  font=("Segoe UI", 9, "bold"),
                  command=ozel_hesapla).pack(side="left", padx=8)
        pencere.bind("<Return>", ozel_hesapla)
        doldur()

    def _kapat(self):
        try:
            if self.db is not None:
                self.db.kapat()
        except Exception:
            pass
        self.parent.destroy()
