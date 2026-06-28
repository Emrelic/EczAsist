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
        ("urun_adi", "Ürün", 280),
        ("barkod", "Barkod", 130),
        ("toplam", "Toplam Adet", 100),
        ("en_yakin_miad", "En Yakın Miad", 120),
        ("parti_sayisi", "Parti Sayısı", 100),
    ],
    "miad": [
        ("urun_adi", "Ürün", 280),
        ("barkod", "Barkod", 130),
        ("parti_no", "Parti / Lot", 130),
        ("miad", "Miad", 120),
        ("toplam", "Adet", 90),
    ],
    "karekod": [
        ("urun_adi", "Ürün", 250),
        ("barkod", "Barkod", 130),
        ("seri_no", "Seri No", 160),
        ("parti_no", "Parti / Lot", 110),
        ("miad", "Miad", 110),
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
        self.root.after(300, self._ilk_acilis_kart_kontrol)

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

        # Araç çubuğu — yerel kart aktarımı / durum
        arac = tk.Frame(cerceve, bg=_BG)
        arac.pack(fill="x", pady=(0, 4))
        self._aktar_btn = tk.Button(
            arac, text="🔄 Kartları Botanik'ten Aktar",
            command=self._kartlari_aktar, bg="#00838F", fg="white", bd=0,
            padx=10, pady=3)
        self._aktar_btn.pack(side="left")
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
        self.giris_entry.bind("<Return>", lambda e: self._okut())
        self.giris_entry.focus_set()
        tk.Button(satir, text="🔍 İsimden Ara", command=self._isimden_ara,
                  bg="#1565C0", fg="white", bd=0, padx=10).pack(side="left")
        tk.Label(satir, text="(Karekod okutucu ile okutun veya barkod yazıp Enter)",
                 bg=_BG, fg="#607D8B", font=("Arial", 9)).pack(side="left", padx=10)

        # İşlem listesi
        liste_fr = tk.Frame(cerceve, bg=_BG)
        liste_fr.pack(fill="both", expand=True)
        kols = ("urun_adi", "barkod", "seri_no", "parti_no", "miad", "adet")
        basliklar = (("urun_adi", "Ürün", 300), ("barkod", "Barkod", 130),
                     ("seri_no", "Seri No", 150), ("parti_no", "Parti", 110),
                     ("miad", "Miad", 110), ("adet", "Adet", 70))
        self.islem_tree = ttk.Treeview(liste_fr, columns=kols, show="headings",
                                       height=6)
        for alan, baslik, gen in basliklar:
            self.islem_tree.heading(alan, text=baslik)
            self.islem_tree.column(alan, width=gen,
                                   anchor="center" if alan in ("adet",) else "w")
        ysb = ttk.Scrollbar(liste_fr, orient="vertical",
                            command=self.islem_tree.yview)
        self.islem_tree.configure(yscrollcommand=ysb.set)
        self.islem_tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

        # Buton satırı
        btn = tk.Frame(cerceve, bg=_BG)
        btn.pack(fill="x", pady=(8, 2))
        tk.Button(btn, text="🗑 Seçili Satırı Çıkar", command=self._secili_cikar,
                  bg="#78909C", fg="white", bd=0, padx=10, pady=4).pack(
            side="left")
        tk.Button(btn, text="🧹 Listeyi Temizle", command=self._listeyi_temizle,
                  bg="#90A4AE", fg="white", bd=0, padx=10, pady=4).pack(
            side="left", padx=6)

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

        tk.Button(ust, text="🔄 Yenile", command=self._stok_yenile,
                  bg="#00796B", fg="white", bd=0, padx=10).pack(side="left",
                                                                padx=10)
        self.ozet_lbl = tk.Label(ust, text="", bg=_BG, fg="#37474F",
                                 font=("Arial", 10, "bold"))
        self.ozet_lbl.pack(side="right")

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

    def _tree_kolonlari_kur(self, gorunum):
        kols = [a for a, _, _ in _GORUNUM_KOLON[gorunum]]
        self.stok_tree["columns"] = kols
        for alan, baslik, gen in _GORUNUM_KOLON[gorunum]:
            self.stok_tree.heading(alan, text=baslik)
            anchor = "center" if alan in ("toplam", "miad", "en_yakin_miad",
                                          "parti_sayisi") else "w"
            self.stok_tree.column(alan, width=gen, anchor=anchor)
        self._aktif_gorunum = gorunum

    # =============================================================== OKUTMA
    def _okut(self):
        if not self.db:
            return
        metin = self.giris_entry.get().strip()
        self.giris_entry.delete(0, "end")
        if not metin:
            return
        c = StokTakipDB.karekod_coz(metin)
        logger.info("Okutuldu ham=%r -> tip=%s barkod=%s seri=%s parti=%s miad=%s",
                    metin, c["tip"], c.get("barkod"), c.get("seri_no"),
                    c.get("parti_no"), c.get("miad"))

        if c["tip"] == "isim":
            self._isimden_ara(prefill=metin)
            return

        kart = self.db.urun_karti_barkoddan(c["barkod"]) if c["barkod"] else None
        urun_adi = kart["UrunAdi"] if kart else f"[Tanımsız: {c['barkod']}]"
        urun_id = kart["UrunId"] if kart else None

        kalem = {
            "urun_id": urun_id,
            "barkod": c["barkod"],
            "urun_adi": urun_adi,
            "seri_no": c.get("seri_no"),
            "parti_no": c.get("parti_no"),
            "miad": c.get("miad"),
            "adet": 1,
            "karekod_ham": metin if c["tip"] == "karekod" else None,
            "kaynak": c["tip"],
        }
        self._pending_ekle(kalem)
        self.giris_entry.focus_set()

    def _isimden_ara(self, prefill=""):
        if not self.db:
            return
        kart = AraDialog(self.root, self.db, prefill).goster()
        if not kart:
            self.giris_entry.focus_set()
            return
        kalem = {
            "urun_id": kart.get("UrunId"),
            "barkod": kart.get("Barkod"),
            "urun_adi": kart.get("UrunAdi"),
            "seri_no": None, "parti_no": None, "miad": None,
            "adet": 1, "karekod_ham": None, "kaynak": "isim",
        }
        self._pending_ekle(kalem)
        self.giris_entry.focus_set()

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

    def _ilk_acilis_kart_kontrol(self):
        """İlk açılışta yerel kart boşsa aktarım öner."""
        if not self.db:
            return
        try:
            if self.db.kart_sayisi() == 0:
                if messagebox.askyesno(
                        "Ürün Kartları",
                        "Yerel veritabanında ürün kartı yok.\n\n"
                        "Botanik EOS'tan ilaç kartları şimdi aktarılsın mı?\n"
                        "(Tek seferlik; sonrasında modül Botanik'e bağlanmadan "
                        "çalışır.)"):
                    self._kartlari_aktar()
        except Exception as e:
            logger.debug("İlk açılış kart kontrolü hatası: %s", e)

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

    def _aktar_bitti(self, n, hata):
        self._aktar_btn.config(state="normal",
                               text="🔄 Kartları Botanik'ten Aktar")
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
        self.islem_tree.insert("", "end", values=(
            kalem["urun_adi"], kalem.get("barkod") or "",
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

    # =============================================================== EKLE/DÜŞ
    def _stoga_ekle(self):
        if not self.db or not self.pending:
            messagebox.showinfo("Stok", "İşlem listesi boş.")
            return
        basari, hata = 0, []
        for kalem in list(self.pending):
            # Karekod/seri veya miad varsa doğrudan ekle; yoksa manuel detay sor
            if not kalem.get("seri_no") and not kalem.get("miad"):
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
            if kalem.get("seri_no"):
                ok, msg = self.db.stok_dus_seri(kalem["seri_no"])
            else:
                partiler = self.db.parti_listesi(
                    urun_id=kalem.get("urun_id"), barkod=kalem.get("barkod"))
                if not partiler:
                    hata.append(f"{kalem['urun_adi']}: stokta yok")
                    continue
                secim = PartiSecDialog(self.root, kalem, partiler).goster()
                if secim is None:
                    continue
                ok, msg = self.db.stok_dus_parti(
                    kalem.get("urun_id"), kalem.get("barkod"),
                    secim["parti_no"], secim["miad"], secim["adet"])
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

        filtre = self.filtre_entry.get()
        if gorunum == "barkod":
            satirlar = self.db.stok_barkod_bazli(filtre)
        elif gorunum == "miad":
            satirlar = self.db.stok_miad_bazli(filtre)
        else:
            satirlar = self.db.stok_karekod_bazli(filtre)

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
            self.stok_tree.insert("", "end", values=degerler,
                                  tags=(tag,) if tag else ())

        self.ozet_lbl.config(
            text=f"Satır: {len(satirlar)}   |   Toplam adet: {toplam_adet}")

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
