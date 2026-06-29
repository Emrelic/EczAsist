"""
Stok Takip Modülü — Arayüz (tam ekran)

ÜST bölüm  : İşlem alanı. Barkod / karekod / isimden ürün okut -> liste ->
             "STOĞA EKLE" veya "STOKTAN DÜŞ".
ALT bölüm  : Mevcut stok listesi. 3 görünüm (Barkod / Miad-Parti / Karekod) +
             isim filtreleme kutusu.

Stok tamamen yerel ve Botanik EOS'tan bağımsızdır (bkz. stok_takip_db.py).
EOS'tan yalnızca ürün kartları (ad / barkod) salt-okuma ile çekilir.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from stok_takip_db import StokTakipDB

logger = logging.getLogger(__name__)

# Görünüm -> (alan, başlık, genişlik) kolonları
_GORUNUM_KOLON = {
    "barkod": [
        ("urun_adi", "Ürün", 260),
        ("birim", "Birim", 80),
        ("barkod", "Barkod", 130),
        ("toplam", "Toplam Adet", 100),
        ("en_yakin_miad", "En Yakın Miad", 120),
        ("parti_sayisi", "Parti Sayısı", 100),
    ],
    "miad": [
        ("urun_adi", "Ürün", 260),
        ("birim", "Birim", 80),
        ("barkod", "Barkod", 130),
        ("parti_no", "Parti / Lot", 130),
        ("miad", "Miad", 120),
        ("toplam", "Adet", 90),
    ],
    "karekod": [
        ("urun_adi", "Ürün", 230),
        ("birim", "Birim", 75),
        ("barkod", "Barkod", 130),
        ("seri_no", "Seri No", 150),
        ("parti_no", "Parti / Lot", 100),
        ("miad", "Miad", 100),
        ("giris_tarih", "Giriş", 150),
    ],
}

_BG = "#ECEFF1"
_HEADER = "#263238"
_YESIL = "#2E7D32"
_KIRMIZI = "#C62828"


def _miad_goster(iso):
    """ISO YYYY-MM-DD -> GG.AA.YYYY (gösterim)."""
    if not iso:
        return ""
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return d.strftime("%d.%m.%Y")
    except Exception:
        return str(iso)


def _miad_parse(metin):
    """Kullanıcı girdisini (GG.AA.YYYY / YYYY-MM-DD / AA.YYYY) ISO'ya çevir."""
    if not metin:
        return None
    s = metin.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%m.%Y", "%m/%Y"):
        try:
            d = datetime.strptime(s, fmt)
            return d.date().isoformat()
        except ValueError:
            continue
    return None


class StokTakipGUI:
    def __init__(self, root, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback
        self.root.title("📦 Stok Takip")
        try:
            self.root.state("zoomed")
        except Exception:
            pass
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.root)
        except Exception:
            pass

        try:
            self.db = StokTakipDB()
        except Exception as e:
            logger.error("Stok DB açılamadı: %s", e)
            messagebox.showerror("Hata", f"Stok veritabanı açılamadı:\n{e}")
            self.db = None

        self.pending = []  # işlem listesindeki kalemler (dict)
        self._aktif_gorunum = None

        self.root.protocol("WM_DELETE_WINDOW", self._kapat)
        self._arayuz()
        self._stok_yenile()
        self._kart_durum_guncelle()
        # Not: Kartlar BİR KEZ "🔄 Botanik'ten Aktar" ile aktarılır; her açılışta
        # otomatik soru SORULMAZ. Kart yoksa üstteki uyarı etiketi yönlendirir.

    # =============================================================== ARAYÜZ
    def _arayuz(self):
        # Başlık çubuğu
        ust = tk.Frame(self.root, bg=_HEADER, height=48)
        ust.pack(fill="x")
        tk.Label(ust, text="📦 Stok Takip", font=("Arial", 15, "bold"),
                 bg=_HEADER, fg="white").pack(side="left", padx=16, pady=8)
        tk.Button(ust, text="Ana Menüye Dön", command=self._kapat,
                  bg="#455A64", fg="white", bd=0, padx=12).pack(
            side="right", padx=16, pady=8)

        # PanedWindow: üst işlem / alt stok
        paned = tk.PanedWindow(self.root, orient="vertical", sashwidth=6,
                               bg="#B0BEC5")
        paned.pack(fill="both", expand=True)

        self._islem_paneli(paned)
        self._stok_paneli(paned)

    # --------------------------------------------------------- ÜST: İŞLEM
    def _islem_paneli(self, paned):
        cerceve = tk.LabelFrame(paned, text=" İşlem — Ürün Okut ",
                                font=("Arial", 11, "bold"), bg=_BG,
                                fg="#263238", padx=10, pady=8)
        paned.add(cerceve, minsize=240)

        # Araç çubuğu — yerel ürün kartı yönetimi (ayarlar)
        arac = tk.Frame(cerceve, bg=_BG)
        arac.pack(fill="x", pady=(0, 4))
        tk.Label(arac, text="Ürün Kartları:", bg=_BG,
                 font=("Arial", 9, "bold"), fg="#37474F").pack(side="left")
        self._aktar_btn = tk.Button(
            arac, text="🔄 Botanik'ten Aktar",
            command=self._kartlari_aktar, bg="#00838F", fg="white", bd=0,
            padx=10, pady=3)
        self._aktar_btn.pack(side="left", padx=(6, 0))
        tk.Button(arac, text="➕ Manuel Kart Ekle",
                  command=self._manuel_kart_ekle, bg="#5E35B1", fg="white",
                  bd=0, padx=10, pady=3).pack(side="left", padx=6)
        self.kart_durum_lbl = tk.Label(arac, text="", bg=_BG, fg="#546E7A",
                                       font=("Arial", 9))
        self.kart_durum_lbl.pack(side="left", padx=10)

        # Okutma satırı
        satir = tk.Frame(cerceve, bg=_BG)
        satir.pack(fill="x", pady=(2, 6))
        tk.Label(satir, text="Barkod / Karekod / İsim:", bg=_BG,
                 font=("Arial", 10, "bold")).pack(side="left")
        self.giris_entry = tk.Entry(satir, font=("Consolas", 12), width=50)
        self.giris_entry.pack(side="left", padx=8)
        self.giris_entry.bind("<Return>", self._giris_return)
        self.giris_entry.bind("<KeyRelease>", self._oneri_guncelle)
        self.giris_entry.bind("<Down>", self._oneri_asagi)
        self.giris_entry.bind("<Up>", self._oneri_yukari)
        self.giris_entry.bind("<Escape>", lambda e: self._oneri_gizle())
        self.giris_entry.bind("<FocusOut>", lambda e: self.giris_entry.after(
            150, self._oneri_gizle))
        self.giris_entry.focus_set()
        tk.Label(satir, text="🔍 isim yazınca öneri açılır",
                 bg=_BG, fg="#90A4AE", font=("Arial", 8)).pack(side="left")

        # Inline öneri (autocomplete) durumu — ayrı pencere yok
        self._oneri_pencere = None
        self._oneri_liste = None
        self._oneri_kayitlar = []
        self._oneri_after_id = None

        # Tek tablet modu — işaretliyken eklenenler TABLET olarak işlenir
        self.tek_tablet_var = tk.BooleanVar(value=False)
        self.tek_tablet_chk = tk.Checkbutton(
            satir, text="💊 Tek tablet olarak ekle/düş",
            variable=self.tek_tablet_var, bg=_BG, activebackground=_BG,
            font=("Arial", 10, "bold"), fg="#6A1B9A",
            selectcolor="#E1BEE7", command=self._tek_tablet_modu_degisti)
        self.tek_tablet_chk.pack(side="left", padx=12)
        self.mod_lbl = tk.Label(satir, text="Mod: KUTU", bg=_BG, fg="#00695C",
                                font=("Arial", 10, "bold"))
        self.mod_lbl.pack(side="left")

        # İşlem listesi
        liste_fr = tk.Frame(cerceve, bg=_BG)
        liste_fr.pack(fill="both", expand=True)
        kols = ("urun_adi", "birim", "barkod", "seri_no", "parti_no", "miad", "adet")
        basliklar = (("urun_adi", "Ürün", 280), ("birim", "Birim", 75),
                     ("barkod", "Barkod", 130),
                     ("seri_no", "Seri No", 150), ("parti_no", "Parti", 110),
                     ("miad", "Miad", 110), ("adet", "Adet", 70))
        self.islem_tree = ttk.Treeview(liste_fr, columns=kols, show="headings",
                                       height=6)
        for alan, baslik, gen in basliklar:
            self.islem_tree.heading(alan, text=baslik)
            self.islem_tree.column(alan, width=gen,
                                   anchor="center" if alan in ("adet", "birim") else "w")
        ysb = ttk.Scrollbar(liste_fr, orient="vertical",
                            command=self.islem_tree.yview)
        self.islem_tree.configure(yscrollcommand=ysb.set)
        self.islem_tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        # Delete / Backspace ile seçili satır(lar)ı işlem listesinden sil
        self.islem_tree.bind("<Delete>", lambda e: self._secili_cikar())
        self.islem_tree.bind("<BackSpace>", lambda e: self._secili_cikar())

        # Buton satırı
        btn = tk.Frame(cerceve, bg=_BG)
        btn.pack(fill="x", pady=(8, 2))
        tk.Button(btn, text="🗑 Seçili Satırı Çıkar (Del)", command=self._secili_cikar,
                  bg="#78909C", fg="white", bd=0, padx=10, pady=4).pack(
            side="left")
        tk.Button(btn, text="🧹 Listeyi Temizle", command=self._listeyi_temizle,
                  bg="#90A4AE", fg="white", bd=0, padx=10, pady=4).pack(
            side="left", padx=6)
        tk.Button(btn, text="📋 Toplu Karekod", command=self._toplu_karekod,
                  bg="#5E35B1", fg="white", bd=0, padx=10, pady=4).pack(
            side="left")

        tk.Button(btn, text="➖  STOKTAN DÜŞ", command=self._stoktan_dus,
                  bg=_KIRMIZI, fg="white", bd=0, padx=18, pady=6,
                  font=("Arial", 11, "bold")).pack(side="right", padx=(6, 0))
        tk.Button(btn, text="➕  STOĞA EKLE", command=self._stoga_ekle,
                  bg=_YESIL, fg="white", bd=0, padx=18, pady=6,
                  font=("Arial", 11, "bold")).pack(side="right")

    # --------------------------------------------------------- ALT: STOK
    def _stok_paneli(self, paned):
        cerceve = tk.LabelFrame(paned, text=" Mevcut Stok ",
                                font=("Arial", 11, "bold"), bg=_BG,
                                fg="#263238", padx=10, pady=8)
        paned.add(cerceve, minsize=240)

        ust = tk.Frame(cerceve, bg=_BG)
        ust.pack(fill="x", pady=(2, 6))
        tk.Label(ust, text="İsim filtrele:", bg=_BG,
                 font=("Arial", 10, "bold")).pack(side="left")
        self.filtre_entry = tk.Entry(ust, font=("Arial", 11), width=30)
        self.filtre_entry.pack(side="left", padx=8)
        self.filtre_entry.bind("<KeyRelease>", lambda e: self._stok_yenile())

        tk.Label(ust, text="   Görünüm:", bg=_BG,
                 font=("Arial", 10, "bold")).pack(side="left")
        self.gorunum_var = tk.StringVar(value="barkod")
        for deger, etiket in (("barkod", "Barkod bazlı"),
                              ("miad", "Miad / Parti bazlı"),
                              ("karekod", "Karekod bazlı")):
            ttk.Radiobutton(ust, text=etiket, value=deger,
                            variable=self.gorunum_var,
                            command=self._stok_yenile).pack(side="left", padx=4)

        tk.Label(ust, text="   Birim:", bg=_BG,
                 font=("Arial", 10, "bold")).pack(side="left")
        self.birim_gor_var = tk.StringVar(value="HEPSI")
        for deger, etiket in (("KUTU", "Kutu"), ("TABLET", "Tek Tablet"),
                              ("HEPSI", "Her İkisi")):
            ttk.Radiobutton(ust, text=etiket, value=deger,
                            variable=self.birim_gor_var,
                            command=self._stok_yenile).pack(side="left", padx=4)

        tk.Button(ust, text="🔄 Yenile", command=self._stok_yenile,
                  bg="#00796B", fg="white", bd=0, padx=10).pack(side="left",
                                                                padx=10)
        tk.Button(ust, text="🗑 Tüm Stoğu Temizle", command=self._tum_stogu_temizle,
                  bg="#B71C1C", fg="white", bd=0, padx=10).pack(side="left")
        self.ozet_lbl = tk.Label(ust, text="", bg=_BG, fg="#37474F",
                                 font=("Arial", 10, "bold"))
        self.ozet_lbl.pack(side="right")

        # Seçim ipucu
        ipucu = tk.Frame(cerceve, bg=_BG)
        ipucu.pack(fill="x")
        tk.Label(ipucu, text="☑ Satır başındaki kutucuktan seç → sağ tık → "
                 "'Seçili olanları stoktan çıkar'", bg=_BG, fg="#78909C",
                 font=("Arial", 9)).pack(side="left")

        # Çoklu seçim durumu
        self._secili_satirlar = set()
        self._satir_kayit = {}

        # Tree
        tree_fr = tk.Frame(cerceve, bg=_BG)
        tree_fr.pack(fill="both", expand=True)
        self.stok_tree = ttk.Treeview(tree_fr, show="headings")
        ysb = ttk.Scrollbar(tree_fr, orient="vertical",
                            command=self.stok_tree.yview)
        self.stok_tree.configure(yscrollcommand=ysb.set)
        self.stok_tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        # Miadı yakın olanı vurgula
        self.stok_tree.tag_configure("kirmizi", background="#FFCDD2")
        self.stok_tree.tag_configure("sari", background="#FFF9C4")
        # Checkbox tıklaması + sağ tık menüsü
        self.stok_tree.bind("<Button-1>", self._stok_tree_tikla)
        self.stok_tree.bind("<Button-3>", self._stok_tree_sag_tik)

    def _tree_kolonlari_kur(self, gorunum):
        # İlk kolon: seçim kutucuğu
        kols = ["sec"] + [a for a, _, _ in _GORUNUM_KOLON[gorunum]]
        self.stok_tree["columns"] = kols
        self.stok_tree.heading("sec", text="☑")
        self.stok_tree.column("sec", width=34, anchor="center", stretch=False)
        for alan, baslik, gen in _GORUNUM_KOLON[gorunum]:
            self.stok_tree.heading(alan, text=baslik)
            anchor = "center" if alan in ("toplam", "miad", "en_yakin_miad",
                                          "parti_sayisi", "birim") else "w"
            self.stok_tree.column(alan, width=gen, anchor=anchor)
        self._aktif_gorunum = gorunum

    # =========================================================== OKUTMA / ARAMA
    def _giris_return(self, event=None):
        """Enter: barkod/karekod→okut; isim→seçili öneriyi al, yoksa öneriyi aç."""
        if not self.db:
            return "break"
        metin = self.giris_entry.get().strip()
        if not metin:
            return "break"
        c = StokTakipDB.karekod_coz(metin)
        if c["tip"] in ("barkod", "karekod"):
            self._oneri_gizle()
            self.giris_entry.delete(0, "end")
            self._okut_kod(c, metin)
        else:  # isim
            if self._oneri_liste is not None and self._oneri_liste.size():
                sel = self._oneri_liste.curselection()
                self._oneri_sec(sel[0] if sel else 0)
            else:
                self._oneri_sorgula()
        return "break"

    def _okut_kod(self, c, metin):
        """Barkod/karekod kalemini pending'e ekle."""
        logger.info("Okutuldu ham=%r -> tip=%s barkod=%s seri=%s parti=%s miad=%s",
                    metin, c["tip"], c.get("barkod"), c.get("seri_no"),
                    c.get("parti_no"), c.get("miad"))
        kart = self.db.urun_karti_barkoddan(c["barkod"]) if c["barkod"] else None
        urun_adi = kart["UrunAdi"] if kart else f"[Tanımsız: {c['barkod']}]"
        urun_id = kart["UrunId"] if kart else None
        tablet = self.tek_tablet_var.get()
        kalem = {
            "urun_id": urun_id, "barkod": c["barkod"], "urun_adi": urun_adi,
            "seri_no": None if tablet else c.get("seri_no"),
            "parti_no": None if tablet else c.get("parti_no"),
            "miad": c.get("miad"), "adet": 1,
            "birim": "TABLET" if tablet else "KUTU",
            "karekod_ham": metin if c["tip"] == "karekod" else None,
            "kaynak": c["tip"],
        }
        if tablet and not self._tablet_miktar_sor(kalem):
            self.giris_entry.focus_set()
            return
        self._pending_ekle(kalem)
        self.giris_entry.focus_set()

    def _kart_pending_ekle(self, kart):
        """İsimden seçilen kartı pending'e ekle (birim moduna göre)."""
        tablet = self.tek_tablet_var.get()
        kalem = {
            "urun_id": kart.get("UrunId"), "barkod": kart.get("Barkod"),
            "urun_adi": kart.get("UrunAdi"),
            "seri_no": None, "parti_no": None, "miad": None,
            "adet": 1, "karekod_ham": None, "kaynak": "isim",
            "birim": "TABLET" if tablet else "KUTU",
        }
        if tablet and not self._tablet_miktar_sor(kalem):
            return
        self._pending_ekle(kalem)

    def _tablet_miktar_sor(self, kalem):
        """Tek tablet modunda kart seçilince miktar (+ opsiyonel miad) popup'ı.
        Onaylanırsa kalem'i günceller ve True döner; iptalde False."""
        detay = TekTabletDialog(self.root, kalem).goster()
        if detay is None:
            return False
        kalem.update(detay)  # adet, miad, parti_no, seri_no, birim
        return True

    # ------------------------------------------ Inline öneri (autocomplete)
    def _oneri_guncelle(self, event=None):
        """KeyRelease: navigasyon tuşlarını atla, kısa debounce ile sorgula."""
        if event is not None and event.keysym in (
                "Up", "Down", "Return", "Escape", "Left", "Right",
                "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        if self._oneri_after_id:
            try:
                self.giris_entry.after_cancel(self._oneri_after_id)
            except Exception:
                pass
        self._oneri_after_id = self.giris_entry.after(120, self._oneri_sorgula)

    def _oneri_sorgula(self):
        self._oneri_after_id = None
        if not self.db:
            return
        metin = self.giris_entry.get().strip()
        c = StokTakipDB.karekod_coz(metin)
        if c["tip"] != "isim" or len(metin) < 2:
            self._oneri_gizle()
            return
        kayitlar = self.db.urun_karti_ara(metin, limit=12)
        if not kayitlar:
            self._oneri_gizle()
            return
        self._oneri_goster(kayitlar)

    def _oneri_goster(self, kayitlar):
        self._oneri_kayitlar = kayitlar
        if (self._oneri_pencere is None
                or not self._oneri_pencere.winfo_exists()):
            self._oneri_pencere = tk.Toplevel(self.root)
            self._oneri_pencere.overrideredirect(True)
            self._oneri_pencere.attributes("-topmost", True)
            self._oneri_liste = tk.Listbox(
                self._oneri_pencere, font=("Arial", 10), height=8,
                activestyle="dotbox", bg="white", highlightthickness=1,
                highlightbackground="#1565C0", selectbackground="#1565C0",
                selectforeground="white")
            self._oneri_liste.pack(fill="both", expand=True)
            self._oneri_liste.bind("<Button-1>", self._oneri_tikla)
            self._oneri_liste.bind("<Double-1>", self._oneri_tikla)
        self._oneri_liste.delete(0, "end")
        for k in kayitlar:
            ad = k.get("UrunAdi") or ""
            bk = k.get("Barkod") or ""
            self._oneri_liste.insert("end", f"{ad}   ·  [{bk}]")
        self.giris_entry.update_idletasks()
        x = self.giris_entry.winfo_rootx()
        y = self.giris_entry.winfo_rooty() + self.giris_entry.winfo_height()
        w = max(self.giris_entry.winfo_width(), 460)
        h = min(len(kayitlar), 8) * 20 + 6
        self._oneri_pencere.geometry(f"{w}x{h}+{x}+{y}")
        self._oneri_pencere.deiconify()
        self._oneri_liste.selection_clear(0, "end")
        self._oneri_liste.selection_set(0)
        self._oneri_liste.activate(0)

    def _oneri_gizle(self):
        if self._oneri_pencere is not None:
            try:
                self._oneri_pencere.destroy()
            except Exception:
                pass
        self._oneri_pencere = None
        self._oneri_liste = None
        self._oneri_kayitlar = []

    def _oneri_asagi(self, event=None):
        if self._oneri_liste is None or not self._oneri_liste.size():
            return
        sel = self._oneri_liste.curselection()
        idx = min((sel[0] + 1) if sel else 0, self._oneri_liste.size() - 1)
        self._oneri_liste.selection_clear(0, "end")
        self._oneri_liste.selection_set(idx)
        self._oneri_liste.activate(idx)
        self._oneri_liste.see(idx)
        return "break"

    def _oneri_yukari(self, event=None):
        if self._oneri_liste is None or not self._oneri_liste.size():
            return
        sel = self._oneri_liste.curselection()
        idx = max((sel[0] - 1) if sel else 0, 0)
        self._oneri_liste.selection_clear(0, "end")
        self._oneri_liste.selection_set(idx)
        self._oneri_liste.activate(idx)
        self._oneri_liste.see(idx)
        return "break"

    def _oneri_tikla(self, event):
        if self._oneri_liste is None:
            return
        idx = self._oneri_liste.nearest(event.y)
        if idx >= 0:
            self._oneri_sec(idx)

    def _oneri_sec(self, idx):
        if 0 <= idx < len(self._oneri_kayitlar):
            kart = self._oneri_kayitlar[idx]
            self._oneri_gizle()
            self.giris_entry.delete(0, "end")
            self._kart_pending_ekle(kart)
            self.giris_entry.focus_set()

    def _tek_tablet_modu_degisti(self):
        tablet = self.tek_tablet_var.get()
        self.mod_lbl.config(text="Mod: TEK TABLET" if tablet else "Mod: KUTU",
                            fg="#6A1B9A" if tablet else "#00695C")

    # ====================================================== YEREL KART AKTARIM
    def _kart_durum_guncelle(self):
        if not self.db:
            return
        try:
            n = self.db.kart_sayisi()
        except Exception:
            n = 0
        if n:
            self.kart_durum_lbl.config(
                text=f"Yerel ürün kartı: {n:,}".replace(",", "."),
                fg="#2E7D32")
        else:
            self.kart_durum_lbl.config(
                text="⚠ Yerel kart yok — önce Botanik'ten aktarın",
                fg="#C62828")

    def _kartlari_aktar(self):
        if not self.db:
            return
        if not messagebox.askyesno(
                "Kart Aktarımı",
                "Botanik EOS'tan tüm ilaç kartları yerel veritabanına "
                "aktarılsın mı?\n(Mevcut yerel kartlar yenilenecek.)"):
            return
        self._aktar_btn.config(state="disabled", text="Aktarılıyor…")
        self.kart_durum_lbl.config(text="Botanik'ten aktarılıyor, lütfen bekleyin…",
                                   fg="#546E7A")
        import threading

        def isle():
            try:
                n = self.db.kartlari_botanikten_aktar()
                self.root.after(0, lambda: self._aktar_bitti(n, None))
            except Exception as e:
                self.root.after(0, lambda: self._aktar_bitti(0, str(e)))

        threading.Thread(target=isle, daemon=True).start()

    def _manuel_kart_ekle(self):
        """Stokta/Botanik'te olmayan ürün için elle kart ekle."""
        if not self.db:
            return
        veri = ManuelKartDialog(self.root).goster()
        if not veri:
            return
        ok, msg = self.db.kart_ekle_manuel(
            veri["barkod"], veri["urun_adi"], veri.get("etiket_fiyat"))
        if ok:
            self._kart_durum_guncelle()
            messagebox.showinfo("Ürün Kartı", "✓ " + msg)
        else:
            messagebox.showwarning("Ürün Kartı", msg)

    def _aktar_bitti(self, n, hata):
        self._aktar_btn.config(state="normal",
                               text="🔄 Botanik'ten Aktar")
        if hata:
            self._kart_durum_guncelle()
            messagebox.showerror("Kart Aktarımı", f"Aktarım başarısız:\n{hata}")
        else:
            self._kart_durum_guncelle()
            messagebox.showinfo(
                "Kart Aktarımı",
                f"✓ {n} ürün kartı yerel veritabanına aktarıldı.")

    def _pending_ekle(self, kalem):
        self.pending.append(kalem)
        birim = "TABLET" if kalem.get("birim") == "TABLET" else "KUTU"
        self.islem_tree.insert("", "end", values=(
            kalem["urun_adi"], birim, kalem.get("barkod") or "",
            kalem.get("seri_no") or "", kalem.get("parti_no") or "",
            _miad_goster(kalem.get("miad")), kalem.get("adet", 1),
        ))

    def _secili_cikar(self):
        sec = self.islem_tree.selection()
        if not sec:
            return
        for iid in sec:
            idx = self.islem_tree.index(iid)
            self.islem_tree.delete(iid)
            if 0 <= idx < len(self.pending):
                self.pending.pop(idx)

    def _listeyi_temizle(self):
        self.pending.clear()
        for iid in self.islem_tree.get_children():
            self.islem_tree.delete(iid)

    def _toplu_karekod(self):
        """Çok satırlı kutuya yapıştırılan karekodları topluca listeye ekle.
        Her satır bir karekod/barkod → KUTU kalemi (seri/parti/miad ile)."""
        if not self.db:
            return
        metin = TopluKarekodDialog(self.root).goster()
        if not metin:
            return
        satirlar = [s.strip() for s in metin.splitlines() if s.strip()]
        if not satirlar:
            return
        mevcut_seri = {k.get("seri_no") for k in self.pending if k.get("seri_no")}
        eklenen = tanimsiz = tekrar = 0
        for ham in satirlar:
            c = StokTakipDB.karekod_coz(ham)
            if c["tip"] == "isim":
                tanimsiz += 1
                continue
            seri = c.get("seri_no")
            if seri and seri in mevcut_seri:
                tekrar += 1
                continue
            kart = self.db.urun_karti_barkoddan(c["barkod"]) if c["barkod"] else None
            urun_adi = kart["UrunAdi"] if kart else f"[Tanımsız: {c['barkod']}]"
            urun_id = kart["UrunId"] if kart else None
            self._pending_ekle({
                "urun_id": urun_id, "barkod": c["barkod"], "urun_adi": urun_adi,
                "seri_no": seri, "parti_no": c.get("parti_no"),
                "miad": c.get("miad"), "adet": 1, "birim": "KUTU",
                "karekod_ham": ham, "kaynak": c["tip"],
            })
            if seri:
                mevcut_seri.add(seri)
            eklenen += 1
        mesaj = f"✓ {eklenen} karekod listeye eklendi."
        if tekrar:
            mesaj += f"\n↔ {tekrar} tekrar atlandı (aynı seri no)."
        if tanimsiz:
            mesaj += f"\n✗ {tanimsiz} satır çözümlenemedi."
        messagebox.showinfo("Toplu Karekod", mesaj)

    # =============================================================== EKLE/DÜŞ
    def _stoga_ekle(self):
        if not self.db or not self.pending:
            messagebox.showinfo("Stok", "İşlem listesi boş.")
            return
        basari, hata = 0, []
        for kalem in list(self.pending):
            if kalem.get("birim") == "TABLET":
                # Tek tablet: adet miktar kutusundan zaten geldi, miad opsiyonel
                # (varsa karekoddan); popup YOK, doğrudan eklenir.
                pass
            elif not kalem.get("seri_no") and not kalem.get("miad"):
                # Kutu ama karekod yok: parti/miad/adet manuel sor
                detay = ManuelGirisDialog(self.root, kalem).goster()
                if detay is None:
                    continue  # kullanıcı iptal etti
                kalem = {**kalem, **detay}
            ok, msg = self.db.stok_ekle(kalem)
            if ok:
                basari += 1
            else:
                hata.append(f"{kalem['urun_adi']}: {msg}")
        self._sonuc_goster("Stoğa ekleme", basari, hata)
        self._listeyi_temizle()
        self._stok_yenile()

    def _stoktan_dus(self):
        if not self.db or not self.pending:
            messagebox.showinfo("Stok", "İşlem listesi boş.")
            return
        basari, hata = 0, []
        for kalem in list(self.pending):
            birim = "TABLET" if kalem.get("birim") == "TABLET" else "KUTU"
            if birim == "KUTU" and kalem.get("seri_no"):
                ok, msg = self.db.stok_dus_seri(kalem["seri_no"])
            else:
                partiler = self.db.parti_listesi(
                    urun_id=kalem.get("urun_id"), barkod=kalem.get("barkod"),
                    birim=birim)
                if not partiler:
                    etiket = "tek tablet" if birim == "TABLET" else "kutu"
                    hata.append(f"{kalem['urun_adi']}: stokta {etiket} yok")
                    continue
                secim = PartiSecDialog(self.root, kalem, partiler).goster()
                if secim is None:
                    continue
                ok, msg = self.db.stok_dus_parti(
                    kalem.get("urun_id"), kalem.get("barkod"),
                    secim["parti_no"], secim["miad"], secim["adet"],
                    birim=birim)
            if ok:
                basari += 1
            else:
                hata.append(f"{kalem['urun_adi']}: {msg}")
        self._sonuc_goster("Stoktan düşme", basari, hata)
        self._listeyi_temizle()
        self._stok_yenile()

    def _sonuc_goster(self, baslik, basari, hata):
        if hata:
            messagebox.showwarning(
                baslik,
                f"✓ Başarılı: {basari}\n✗ Hatalı: {len(hata)}\n\n"
                + "\n".join(hata[:15]))
        else:
            messagebox.showinfo(baslik, f"✓ {basari} işlem tamamlandı.")

    # =============================================================== LİSTE
    def _stok_yenile(self):
        if not self.db:
            return
        gorunum = self.gorunum_var.get()
        if gorunum != self._aktif_gorunum:
            self._tree_kolonlari_kur(gorunum)
        for iid in self.stok_tree.get_children():
            self.stok_tree.delete(iid)
        # Yenilemede seçim sıfırlanır (satır id'leri değişir)
        self._secili_satirlar = set()
        self._satir_kayit = {}

        filtre = self.filtre_entry.get()
        birim = self.birim_gor_var.get()
        birim = None if birim == "HEPSI" else birim
        if gorunum == "barkod":
            satirlar = self.db.stok_barkod_bazli(filtre, birim=birim)
        elif gorunum == "miad":
            satirlar = self.db.stok_miad_bazli(filtre, birim=birim)
        else:
            satirlar = self.db.stok_karekod_bazli(filtre, birim=birim)

        toplam_adet = 0
        bugun = datetime.now().date()
        for r in satirlar:
            d = dict(r)
            toplam_adet += d.get("toplam") or d.get("adet") or 0
            degerler = []
            for alan, _, _ in _GORUNUM_KOLON[gorunum]:
                v = d.get(alan)
                if alan in ("miad", "en_yakin_miad"):
                    v = _miad_goster(v)
                elif alan == "giris_tarih" and v:
                    v = str(v).replace("T", " ")[:16]
                degerler.append("" if v is None else v)
            tag = self._miad_tag(d.get("miad") or d.get("en_yakin_miad"), bugun)
            iid = self.stok_tree.insert(
                "", "end", values=["☐"] + degerler,
                tags=(tag,) if tag else ())
            self._satir_kayit[iid] = d  # kaynak kayıt (çıkarma için)

        self.ozet_lbl.config(
            text=f"Satır: {len(satirlar)}   |   Toplam adet: {toplam_adet}")

    # ===================================================== ÇOKLU SEÇİM / ÇIKAR
    def _stok_tree_tikla(self, event):
        """Yalnız ilk kolona (checkbox) tıklayınca seçimi değiştir."""
        if self.stok_tree.identify_region(event.x, event.y) != "cell":
            return
        if self.stok_tree.identify_column(event.x) != "#1":
            return
        iid = self.stok_tree.identify_row(event.y)
        if iid:
            self._satir_sec_toggle(iid)

    def _satir_sec_toggle(self, iid):
        if iid in self._secili_satirlar:
            self._secili_satirlar.discard(iid)
            self.stok_tree.set(iid, "sec", "☐")
        else:
            self._secili_satirlar.add(iid)
            self.stok_tree.set(iid, "sec", "☑")

    def _secimi_temizle(self):
        for iid in list(self._secili_satirlar):
            if self.stok_tree.exists(iid):
                self.stok_tree.set(iid, "sec", "☐")
        self._secili_satirlar = set()

    def _stok_tree_sag_tik(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"➖ Seçili olanları stoktan çıkar "
                         f"({len(self._secili_satirlar)})",
                         command=self._secili_stoktan_cikar)
        menu.add_separator()
        menu.add_command(label="Seçimi temizle", command=self._secimi_temizle)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _secili_stoktan_cikar(self):
        if not self.db:
            return
        if not self._secili_satirlar:
            messagebox.showinfo(
                "Stoktan Çıkar",
                "Önce satır başındaki ☐ kutucuklarından seçim yapın.")
            return
        n = len(self._secili_satirlar)
        if not messagebox.askyesno(
                "Stoktan Çıkar",
                f"Seçili {n} satırın temsil ettiği stok çıkarılacak.\n"
                "Onaylıyor musunuz?"):
            return
        gorunum = self.gorunum_var.get()
        basari, hata = 0, []
        for iid in list(self._secili_satirlar):
            d = self._satir_kayit.get(iid)
            if not d:
                continue
            try:
                if gorunum == "karekod":
                    ok, msg = self.db.stok_dus_kalem(d.get("id"))
                elif gorunum == "miad":
                    ok, msg = self.db.stok_dus_parti(
                        d.get("urun_id"), d.get("barkod"), d.get("parti_no"),
                        d.get("miad"), d.get("toplam") or 0,
                        birim=d.get("birim"))
                else:  # barkod aggregate -> ürün+birim tüm partiler
                    say = self.db.stok_dus_urun_birim(
                        d.get("urun_id"), d.get("barkod"), d.get("birim"))
                    ok, msg = (say > 0), f"{say} kayıt"
            except Exception as e:
                ok, msg = False, str(e)
            if ok:
                basari += 1
            else:
                hata.append(f"{d.get('urun_adi')}: {msg}")
        self._sonuc_goster("Stoktan çıkarma", basari, hata)
        self._stok_yenile()

    def _tum_stogu_temizle(self):
        if not self.db:
            return
        # 1. onay
        if not messagebox.askyesno(
                "Tüm Stoğu Temizle",
                "TÜM stok temizlenecek.\nDevam edilsin mi?"):
            return
        # 2. onay (geri dönüşü vurgula)
        if not messagebox.askyesno(
                "Son Onay — Tüm Stok Silinecek",
                "⚠ TÜM STOK STOKTAN ÇIKARILACAK!\n\n"
                "Bu işlem mevcut stoğun tamamını boşaltır.\n"
                "Gerçekten onaylıyor musunuz?",
                icon="warning"):
            return
        n = self.db.tum_stogu_temizle()
        messagebox.showinfo("Tüm Stok",
                            f"✓ {n} stok kaydı temizlendi.")
        self._stok_yenile()

    def _miad_tag(self, iso, bugun):
        if not iso:
            return ""
        try:
            d = datetime.strptime(str(iso)[:10], "%Y-%m-%d").date()
        except Exception:
            return ""
        kalan = (d - bugun).days
        if kalan < 0:
            return "kirmizi"
        if kalan <= 90:
            return "sari"
        return ""

    # =============================================================== KAPAT
    def _kapat(self):
        try:
            if self.db:
                self.db.kapat()
        except Exception:
            pass
        try:
            if callable(self.ana_menu_callback):
                self.ana_menu_callback()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


# ====================================================================== DİYALOGLAR
class AraDialog:
    """İsimden ürün kartı arama penceresi (EOS salt-okuma)."""

    def __init__(self, parent, db, prefill=""):
        self.db = db
        self.secim = None
        self.top = tk.Toplevel(parent)
        self.top.title("Ürün Kartı Ara")
        self.top.geometry("640x440")
        self.top.transient(parent)
        self.top.grab_set()

        ust = tk.Frame(self.top, padx=10, pady=8)
        ust.pack(fill="x")
        tk.Label(ust, text="Ürün adı:", font=("Arial", 10, "bold")).pack(
            side="left")
        self.entry = tk.Entry(ust, font=("Arial", 11), width=36)
        self.entry.pack(side="left", padx=8)
        self.entry.insert(0, prefill)
        self.entry.bind("<Return>", lambda e: self._ara())
        tk.Button(ust, text="🔍 Ara", command=self._ara,
                  bg="#1565C0", fg="white", bd=0, padx=12).pack(side="left")

        fr = tk.Frame(self.top, padx=10)
        fr.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(fr, columns=("ad", "barkod"),
                                 show="headings")
        self.tree.heading("ad", text="Ürün Adı")
        self.tree.heading("barkod", text="Barkod")
        self.tree.column("ad", width=420)
        self.tree.column("barkod", width=150)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb = ttk.Scrollbar(fr, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._sec())

        alt = tk.Frame(self.top, pady=8)
        alt.pack(fill="x")
        tk.Button(alt, text="Seç", command=self._sec, bg="#2E7D32",
                  fg="white", bd=0, padx=16, pady=4).pack(side="right", padx=10)
        tk.Button(alt, text="İptal", command=self.top.destroy, bg="#90A4AE",
                  fg="white", bd=0, padx=16, pady=4).pack(side="right")

        self._sonuclar = []
        self.entry.focus_set()
        if prefill:
            self._ara()

    def _ara(self):
        ad = self.entry.get().strip()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        if len(ad) < 2:
            return
        self._sonuclar = self.db.urun_karti_ara(ad, limit=100)
        for r in self._sonuclar:
            self.tree.insert("", "end",
                             values=(r.get("UrunAdi"), r.get("Barkod") or ""))

    def _sec(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self._sonuclar):
            self.secim = self._sonuclar[idx]
        self.top.destroy()

    def goster(self):
        self.top.wait_window()
        return self.secim


class ManuelKartDialog:
    """Elle ürün kartı ekleme (barkod + ürün adı + etiket fiyatı)."""

    def __init__(self, parent):
        self.sonuc = None
        self.top = tk.Toplevel(parent)
        self.top.title("Manuel Ürün Kartı Ekle")
        self.top.geometry("440x280")
        self.top.transient(parent)
        self.top.grab_set()

        tk.Label(self.top, text="➕ Yeni Ürün Kartı", font=("Arial", 12, "bold"),
                 fg="#5E35B1").pack(pady=(14, 2))
        tk.Label(self.top, text="Stokta/Botanik'te olmayan ürün için",
                 fg="#7E57C2", font=("Arial", 9)).pack()
        gr = tk.Frame(self.top)
        gr.pack(pady=10)

        tk.Label(gr, text="Barkod *:", anchor="e", width=14).grid(
            row=0, column=0, pady=5, sticky="e")
        self.barkod = tk.Entry(gr, font=("Consolas", 11), width=24)
        self.barkod.grid(row=0, column=1, pady=5)

        tk.Label(gr, text="Ürün adı *:", anchor="e", width=14).grid(
            row=1, column=0, pady=5, sticky="e")
        self.ad = tk.Entry(gr, font=("Arial", 11), width=24)
        self.ad.grid(row=1, column=1, pady=5)

        tk.Label(gr, text="Etiket fiyatı:", anchor="e", width=14).grid(
            row=2, column=0, pady=5, sticky="e")
        self.fiyat = tk.Entry(gr, font=("Arial", 11), width=24)
        self.fiyat.grid(row=2, column=1, pady=5)
        tk.Label(gr, text="(opsiyonel)", fg="#90A4AE",
                 font=("Arial", 8)).grid(row=2, column=2, sticky="w")

        alt = tk.Frame(self.top)
        alt.pack(pady=14)
        tk.Button(alt, text="Kaydet", command=self._tamam, bg="#5E35B1",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left", padx=6)
        tk.Button(alt, text="İptal", command=self.top.destroy, bg="#90A4AE",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left")
        self.barkod.focus_set()

    def _tamam(self):
        barkod = self.barkod.get().strip()
        ad = self.ad.get().strip()
        if not barkod:
            messagebox.showwarning("Eksik", "Barkod zorunlu.", parent=self.top)
            return
        if not ad:
            messagebox.showwarning("Eksik", "Ürün adı zorunlu.", parent=self.top)
            return
        self.sonuc = {"barkod": barkod, "urun_adi": ad,
                      "etiket_fiyat": self.fiyat.get().strip() or None}
        self.top.destroy()

    def goster(self):
        self.top.wait_window()
        return self.sonuc


class ManuelGirisDialog:
    """Karekodsuz girişte parti / miad / adet bilgisini elle al."""

    def __init__(self, parent, kalem):
        self.sonuc = None
        self.top = tk.Toplevel(parent)
        self.top.title("Stok Girişi — Detay")
        self.top.geometry("420x260")
        self.top.transient(parent)
        self.top.grab_set()

        tk.Label(self.top, text=kalem["urun_adi"], font=("Arial", 11, "bold"),
                 wraplength=380).pack(pady=(12, 8))
        gr = tk.Frame(self.top)
        gr.pack(pady=4)

        tk.Label(gr, text="Parti / Lot:", anchor="e", width=14).grid(
            row=0, column=0, pady=4, sticky="e")
        self.parti = tk.Entry(gr, font=("Arial", 11), width=20)
        self.parti.grid(row=0, column=1, pady=4)

        tk.Label(gr, text="Miad (GG.AA.YYYY):", anchor="e", width=14).grid(
            row=1, column=0, pady=4, sticky="e")
        self.miad = tk.Entry(gr, font=("Arial", 11), width=20)
        self.miad.grid(row=1, column=1, pady=4)

        tk.Label(gr, text="Adet:", anchor="e", width=14).grid(
            row=2, column=0, pady=4, sticky="e")
        self.adet = tk.Spinbox(gr, from_=1, to=100000, font=("Arial", 11),
                               width=8)
        self.adet.grid(row=2, column=1, pady=4, sticky="w")

        alt = tk.Frame(self.top)
        alt.pack(pady=14)
        tk.Button(alt, text="Ekle", command=self._tamam, bg="#2E7D32",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left", padx=6)
        tk.Button(alt, text="İptal", command=self.top.destroy, bg="#90A4AE",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left")
        self.parti.focus_set()

    def _tamam(self):
        miad_iso = _miad_parse(self.miad.get())
        if self.miad.get().strip() and miad_iso is None:
            messagebox.showwarning("Miad", "Miad biçimi geçersiz "
                                   "(örn. 30.11.2026).", parent=self.top)
            return
        try:
            adet = int(self.adet.get())
        except ValueError:
            adet = 1
        self.sonuc = {"parti_no": self.parti.get().strip() or None,
                      "miad": miad_iso, "adet": max(1, adet)}
        self.top.destroy()

    def goster(self):
        self.top.wait_window()
        return self.sonuc


class TopluKarekodDialog:
    """Çok satırlı karekod girişi — her satıra bir karekod yapıştır."""

    def __init__(self, parent):
        self.sonuc = None
        self.top = tk.Toplevel(parent)
        self.top.title("Toplu Karekod Girişi")
        self.top.geometry("640x470")
        self.top.transient(parent)
        self.top.grab_set()

        tk.Label(self.top, text="📋 Toplu Karekod Girişi",
                 font=("Arial", 12, "bold"), fg="#5E35B1").pack(pady=(12, 2))
        tk.Label(self.top, text="Her satıra bir karekod (veya barkod) yapıştırın. "
                 "Her satır bir kutu olarak listeye eklenir.",
                 fg="#546E7A", font=("Arial", 9)).pack()

        fr = tk.Frame(self.top)
        fr.pack(fill="both", expand=True, padx=10, pady=8)
        self.text = tk.Text(fr, font=("Consolas", 10), wrap="none", height=16,
                            undo=True)
        ysb = ttk.Scrollbar(fr, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=ysb.set)
        self.text.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.text.focus_set()

        alt = tk.Frame(self.top)
        alt.pack(pady=10)
        tk.Button(alt, text="Listeye Ekle", command=self._tamam, bg="#2E7D32",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left", padx=6)
        tk.Button(alt, text="İptal", command=self.top.destroy, bg="#90A4AE",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left")

    def _tamam(self):
        self.sonuc = self.text.get("1.0", "end")
        self.top.destroy()

    def goster(self):
        self.top.wait_window()
        return self.sonuc


class TekTabletDialog:
    """Tek tablet girişi: miad OPSİYONEL (boş bırakılabilir) + adet."""

    def __init__(self, parent, kalem):
        self.sonuc = None
        self.top = tk.Toplevel(parent)
        self.top.title("Tek Tablet Stok Girişi")
        self.top.geometry("420x240")
        self.top.transient(parent)
        self.top.grab_set()

        tk.Label(self.top, text="💊 " + kalem["urun_adi"],
                 font=("Arial", 11, "bold"), wraplength=380,
                 fg="#6A1B9A").pack(pady=(12, 2))
        tk.Label(self.top, text="Tek tablet (açılmış kutu) olarak eklenecek",
                 fg="#7B1FA2", font=("Arial", 9)).pack()
        gr = tk.Frame(self.top)
        gr.pack(pady=8)

        tk.Label(gr, text="Miad (opsiyonel):", anchor="e", width=16).grid(
            row=0, column=0, pady=5, sticky="e")
        self.miad = tk.Entry(gr, font=("Arial", 11), width=18)
        self.miad.grid(row=0, column=1, pady=5)
        # Karekoddan miad geldiyse ön-doldur (yine de silinebilir)
        if kalem.get("miad"):
            self.miad.insert(0, _miad_goster(kalem["miad"]))

        tk.Label(gr, text="Tablet adedi:", anchor="e", width=16).grid(
            row=1, column=0, pady=5, sticky="e")
        self.adet = tk.Spinbox(gr, from_=1, to=100000, font=("Arial", 11),
                               width=8)
        self.adet.grid(row=1, column=1, pady=5, sticky="w")

        alt = tk.Frame(self.top)
        alt.pack(pady=14)
        tk.Button(alt, text="Ekle", command=self._tamam, bg="#6A1B9A",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left", padx=6)
        tk.Button(alt, text="İptal", command=self.top.destroy, bg="#90A4AE",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left")
        self.adet.focus_set()

    def _tamam(self):
        ham = self.miad.get().strip()
        miad_iso = None
        if ham:
            miad_iso = _miad_parse(ham)
            if miad_iso is None:
                messagebox.showwarning(
                    "Miad", "Miad biçimi geçersiz (örn. 30.11.2026) "
                    "ya da boş bırakın.", parent=self.top)
                return
        try:
            adet = int(self.adet.get())
        except ValueError:
            adet = 1
        self.sonuc = {"miad": miad_iso, "adet": max(1, adet),
                      "parti_no": None, "seri_no": None, "birim": "TABLET"}
        self.top.destroy()

    def goster(self):
        self.top.wait_window()
        return self.sonuc


class PartiSecDialog:
    """Stoktan düşerken mevcut partiyi/miadı seçtir + adet."""

    def __init__(self, parent, kalem, partiler):
        self.sonuc = None
        self.partiler = partiler
        self.top = tk.Toplevel(parent)
        self.top.title("Stoktan Düş — Parti Seç")
        self.top.geometry("560x380")
        self.top.transient(parent)
        self.top.grab_set()

        tk.Label(self.top, text=kalem["urun_adi"], font=("Arial", 11, "bold"),
                 wraplength=520).pack(pady=(12, 6))
        tk.Label(self.top, text="Düşülecek partiyi seçin:",
                 fg="#546E7A").pack()

        fr = tk.Frame(self.top, padx=10)
        fr.pack(fill="both", expand=True, pady=6)
        self.tree = ttk.Treeview(fr, columns=("parti", "miad", "mevcut"),
                                 show="headings", height=8)
        self.tree.heading("parti", text="Parti / Lot")
        self.tree.heading("miad", text="Miad")
        self.tree.heading("mevcut", text="Mevcut Adet")
        self.tree.column("parti", width=200)
        self.tree.column("miad", width=140, anchor="center")
        self.tree.column("mevcut", width=120, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        ysb = ttk.Scrollbar(fr, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        ysb.pack(side="right", fill="y")
        for p in partiler:
            self.tree.insert("", "end", values=(
                p.get("parti_no") or "", _miad_goster(p.get("miad")),
                p.get("toplam")))
        ilk = self.tree.get_children()
        if ilk:
            self.tree.selection_set(ilk[0])

        alt = tk.Frame(self.top)
        alt.pack(pady=10)
        tk.Label(alt, text="Adet:").pack(side="left")
        self.adet = tk.Spinbox(alt, from_=1, to=100000, width=8,
                               font=("Arial", 11))
        self.adet.pack(side="left", padx=8)
        tk.Button(alt, text="Düş", command=self._tamam, bg="#C62828",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left", padx=6)
        tk.Button(alt, text="İptal", command=self.top.destroy, bg="#90A4AE",
                  fg="white", bd=0, padx=18, pady=5).pack(side="left")

    def _tamam(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seçim", "Bir parti seçin.", parent=self.top)
            return
        idx = self.tree.index(sel[0])
        p = self.partiler[idx]
        try:
            adet = int(self.adet.get())
        except ValueError:
            adet = 1
        if adet > (p.get("toplam") or 0):
            messagebox.showwarning("Adet", "Mevcut stoktan fazla düşülemez.",
                                   parent=self.top)
            return
        self.sonuc = {"parti_no": p.get("parti_no"), "miad": p.get("miad"),
                      "adet": max(1, adet)}
        self.top.destroy()

    def goster(self):
        self.top.wait_window()
        return self.sonuc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    StokTakipGUI(root, ana_menu_callback=lambda: None)
    root.mainloop()
