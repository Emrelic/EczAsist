"""
Hibrit Siparişçi — Kademeli Sepete Gönderme
=============================================
EczAsist'in sipariş listesi (siparis_db.kesin_siparisler) + Fatih Siparişçi'nin
depo otomasyonu (selenium tabanlı login + barkod arama + sepete ekleme).

Akış (kademeli düşürme):
1. Aktif sipariş çalışması yüklenir (UrunAdi, Barkod, Miktar).
2. Kullanıcı depo öncelik sırasını belirler (varsayılan .env DEPO_SIRALAMA).
3. "Depoları Aç & Giriş Yap" → Fatih MainController._init_depolar() ile aktif
   depo siteleri açılır + login.
4. "Sepete Gönder":
   - kalanlar = tüm satırlar
   - 1. depo için: her satırda search_barcode + add_to_cart → başarılılar düşer
   - 2. depo için: yalnız ekleyemediklerimiz denenir
   - ... taa ki tüm depolar bitsin veya liste tükensin
5. Final rapor: her depodan kaç eklendi, hiçbir depoda bulunamayanların listesi.

Tarama (stok karşılaştırma) YOK — kullanıcı ilaç + miktar zaten belirlemiş,
depolar sadece yürütme tarafı.

Login bilgileri: Fatih'in config/.env'sinden okunur.
"""

import os
import sys
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Fatih Siparişçi kurulu dizini ──────────────────────────────────────────
SIPARISCI_KURULU_DIZIN = Path(os.environ.get("LOCALAPPDATA", "")) / "Siparisci"
SIPARISCI_ENV = SIPARISCI_KURULU_DIZIN / "config" / ".env"

# Tüm depolar (Fatih'in DEFAULT_DEPO_ORDER'ı ile aynı)
TUM_DEPOLAR = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]

DEPO_GORUNEN_AD = {
    "alliance": "Alliance",
    "selcuk": "Selçuk",
    "yusufpasa": "Yusuf Paşa",
    "iskoop": "İskoop",
    "bursa": "Bursa",
    "farmazon": "Farmazon",
    "sancak": "Sancak",
}


def _fatih_path_ekle() -> bool:
    """Fatih kurulumunu sys.path'e ekle"""
    if not SIPARISCI_KURULU_DIZIN.exists():
        return False
    p = str(SIPARISCI_KURULU_DIZIN)
    if p not in sys.path:
        sys.path.insert(0, p)
    return True


def _env_yukle():
    """Fatih'in .env'sini yükle"""
    try:
        from dotenv import load_dotenv
        if SIPARISCI_ENV.exists():
            load_dotenv(SIPARISCI_ENV, override=False)
    except ImportError:
        logger.error("python-dotenv yüklü değil")


def _credentials_olustur() -> dict:
    """Fatih formatında credentials dict'i"""
    return {
        "alliance": {
            "eczane_kodu": os.getenv("ALLIANCE_ECZANE_KODU", ""),
            "username": os.getenv("ALLIANCE_USERNAME", ""),
            "password": os.getenv("ALLIANCE_PASSWORD", ""),
        },
        "selcuk": {
            "hesap_kodu": os.getenv("SELCUK_HESAP_KODU", ""),
            "username": os.getenv("SELCUK_USERNAME", ""),
            "password": os.getenv("SELCUK_PASSWORD", ""),
        },
        "yusufpasa": {
            "eczane_kodu": os.getenv("YUSUFPASA_ECZANE_KODU", ""),
            "username": os.getenv("YUSUFPASA_USERNAME", ""),
            "password": os.getenv("YUSUFPASA_PASSWORD", ""),
        },
        "iskoop": {
            "username": os.getenv("ISKOOP_USERNAME", ""),
            "password": os.getenv("ISKOOP_PASSWORD", ""),
        },
        "bursa": {
            "username": os.getenv("BURSA_USERNAME", ""),
            "password": os.getenv("BURSA_PASSWORD", ""),
        },
        "farmazon": {
            "username": os.getenv("FARMAZON_USERNAME", ""),
            "password": os.getenv("FARMAZON_PASSWORD", ""),
        },
        "sancak": {
            "username": os.getenv("SANCAK_USERNAME", ""),
            "password": os.getenv("SANCAK_PASSWORD", ""),
        },
    }


def _env_depo_siralamasi() -> list[str]:
    """Fatih'in .env'sindeki DEPO_SIRALAMA değerini parse et"""
    raw = os.getenv("DEPO_SIRALAMA", "")
    if not raw:
        return TUM_DEPOLAR.copy()
    sirali = [d.strip().lower() for d in raw.split(",") if d.strip()]
    sirali = [d for d in sirali if d in TUM_DEPOLAR]
    # Eksik depoları sona ekle (kullanıcı çıkardıysa görünmesin ama referansta kalsın)
    for d in TUM_DEPOLAR:
        if d not in sirali:
            sirali.append(d)
    return sirali


def _depo_kullanilabilir_mi(depo_key: str, creds: dict) -> bool:
    """Bu depo için login bilgileri tam mı?"""
    c = creds.get(depo_key, {})
    if depo_key == "alliance":
        return bool(c.get("eczane_kodu") and c.get("username") and c.get("password"))
    if depo_key == "selcuk":
        return bool(c.get("hesap_kodu") and c.get("username") and c.get("password"))
    if depo_key == "yusufpasa":
        return bool(c.get("eczane_kodu") and c.get("username") and c.get("password"))
    return bool(c.get("username") and c.get("password"))


class HibritSiparisciGUI:
    """Hibrit Siparişçi — Kademeli sepete gönderme"""

    def __init__(self, root):
        self.root = root
        self.root.title("Hibrit Siparişçi — Liste → Depolara Kademeli Sepete Gönder")

        # State
        self.fatih_hazir = False
        self.controller = None
        self.aktif_calisma = None
        self.siparisler = []  # list of dict
        self.worker_thread = None
        self.iptal_istendi = False
        self.depo_sirasi = []  # ['selcuk', 'alliance', ...]
        self.credentials = {}

        # Fatih kurulum kontrolü
        if not _fatih_path_ekle():
            self._fatih_yok_goster()
            return

        _env_yukle()
        self.credentials = _credentials_olustur()
        self.depo_sirasi = [
            d for d in _env_depo_siralamasi()
            if _depo_kullanilabilir_mi(d, self.credentials)
        ]

        # Fatih MainController import test
        try:
            from src.controller import MainController  # noqa: F401
            self.fatih_hazir = True
        except Exception as e:
            logger.error(f"Fatih import hatası: {e}")
            self._fatih_import_hatasi_goster(e)
            return

        self._arayuz_olustur()
        self.root.after(200, self._aktif_calismayi_yukle)

    # ─────────────────────────────────────────────────────────────────────
    # Hata göstergeleri
    # ─────────────────────────────────────────────────────────────────────
    def _fatih_yok_goster(self):
        for w in self.root.winfo_children():
            w.destroy()
        frm = tk.Frame(self.root, padx=40, pady=40)
        frm.pack(fill="both", expand=True)
        tk.Label(
            frm,
            text="⚠️  Fatih Siparişçi kurulu değil",
            font=("Arial", 16, "bold"),
            fg="#E65100",
        ).pack(pady=(20, 10))
        tk.Label(
            frm,
            text=(
                "Hibrit Siparişçi, depo otomasyonu için Fatih Siparişçi'yi kullanır.\n\n"
                f"Beklenen kurulum yolu:\n{SIPARISCI_KURULU_DIZIN}\n\n"
                "Lütfen önce SiparisciKurulum.exe'yi çalıştırın."
            ),
            font=("Arial", 10),
            justify="center",
        ).pack(pady=10)
        tk.Button(frm, text="Kapat", command=self.root.destroy, padx=20, pady=8).pack(pady=20)

    def _fatih_import_hatasi_goster(self, hata):
        for w in self.root.winfo_children():
            w.destroy()
        frm = tk.Frame(self.root, padx=40, pady=40)
        frm.pack(fill="both", expand=True)
        tk.Label(
            frm,
            text="⚠️  Fatih Siparişçi modülleri yüklenemedi",
            font=("Arial", 14, "bold"),
            fg="#C62828",
        ).pack(pady=(20, 10))
        tk.Label(
            frm,
            text=f"Hata:\n\n{hata}\n\n"
                 "Eksik paket (selenium, pywinauto vb.) olabilir.\n"
                 "Fatih Siparişçi'yi bir kez çalıştırıp paketlerin yüklü olmasını sağlayın.",
            font=("Arial", 10),
            justify="left",
            wraplength=600,
        ).pack(pady=10)
        tk.Button(frm, text="Kapat", command=self.root.destroy, padx=20, pady=8).pack(pady=20)

    # ─────────────────────────────────────────────────────────────────────
    # Arayüz
    # ─────────────────────────────────────────────────────────────────────
    def _arayuz_olustur(self):
        # Üst bilgi
        ust = tk.Frame(self.root, bg="#00695C", padx=12, pady=8)
        ust.pack(fill="x", side="top")
        self.lbl_calisma = tk.Label(
            ust, text="Çalışma yükleniyor...",
            font=("Arial", 11, "bold"), bg="#00695C", fg="white",
        )
        self.lbl_calisma.pack(side="left")
        self.lbl_ist = tk.Label(
            ust, text="", font=("Arial", 9), bg="#00695C", fg="#B2DFDB",
        )
        self.lbl_ist.pack(side="left", padx=20)
        tk.Button(
            ust, text="↻ Listeyi Yenile",
            command=self._aktif_calismayi_yukle, font=("Arial", 9),
        ).pack(side="right")

        # Tarayıcı modu satırı
        mode_row = tk.Frame(self.root, padx=12, pady=4)
        mode_row.pack(fill="x")
        tk.Label(mode_row, text="Tarayıcı:", font=("Arial", 9, "bold")).pack(side="left")
        env_mode = os.getenv("BROWSER_MODE", "tabs")
        self.var_mode = tk.StringVar(value=env_mode)
        tk.Radiobutton(
            mode_row, text="Paralel (her depo ayrı pencere)",
            variable=self.var_mode, value="windows",
        ).pack(side="left", padx=(5, 0))
        tk.Radiobutton(
            mode_row, text="Sıralı (tek tarayıcı, tab'lar)",
            variable=self.var_mode, value="tabs",
        ).pack(side="left")

        # Aksiyon butonları
        self.btn_depo_ac = tk.Button(
            mode_row, text="🌐  Depoları Aç & Giriş Yap",
            command=self._depolari_ac,
            bg="#1565C0", fg="white",
            font=("Arial", 10, "bold"), padx=12, pady=6, cursor="hand2",
        )
        self.btn_depo_ac.pack(side="left", padx=20)

        self.btn_gonder = tk.Button(
            mode_row, text="🛒  Sepete Gönder (Kademeli)",
            command=self._sepete_gonder_baslat,
            bg="#2E7D32", fg="white",
            font=("Arial", 10, "bold"), padx=14, pady=6,
            state="disabled", cursor="hand2",
        )
        self.btn_gonder.pack(side="left", padx=4)

        self.btn_iptal = tk.Button(
            mode_row, text="✖ İptal",
            command=self._iptal_et,
            bg="#C62828", fg="white",
            padx=10, pady=6, state="disabled",
        )
        self.btn_iptal.pack(side="right", padx=4)

        # Ana içerik: sol depo sırası, sağ treeview
        main = tk.Frame(self.root, padx=12, pady=8)
        main.pack(fill="both", expand=True)

        # ─── Sol: Depo Sırası ───
        sol = tk.LabelFrame(main, text="Depo Öncelik Sırası", padx=8, pady=6)
        sol.pack(side="left", fill="y")

        tk.Label(
            sol,
            text="Yukarıdakiler önce denenir.\nEkleyemediği ilaçlar bir sonraki\ndepoya iner (kademeli).",
            font=("Arial", 8), fg="#555", justify="left",
        ).pack(anchor="w", pady=(0, 6))

        lst_frame = tk.Frame(sol)
        lst_frame.pack(fill="both", expand=True)

        self.lst_depo = tk.Listbox(
            lst_frame, height=10, width=20,
            font=("Arial", 10), exportselection=False,
            selectmode="single",
        )
        self.lst_depo.pack(side="left", fill="both", expand=True)

        btn_col = tk.Frame(lst_frame)
        btn_col.pack(side="left", fill="y", padx=(4, 0))
        tk.Button(
            btn_col, text="▲", width=3,
            command=self._depo_yukari, font=("Arial", 11, "bold"),
        ).pack(pady=2)
        tk.Button(
            btn_col, text="▼", width=3,
            command=self._depo_asagi, font=("Arial", 11, "bold"),
        ).pack(pady=2)

        tk.Button(
            sol, text="↺ .env sırasına dön",
            command=self._depo_sirasi_resetle,
            font=("Arial", 8),
        ).pack(fill="x", pady=(6, 0))

        # Bilgi etiketi: kaç depo aktif
        self.lbl_depo_bilgi = tk.Label(
            sol, text="", font=("Arial", 8), fg="#777", wraplength=180, justify="left",
        )
        self.lbl_depo_bilgi.pack(fill="x", pady=(6, 0))

        self._depo_listbox_doldur()

        # ─── Sağ: Treeview ───
        sag = tk.Frame(main)
        sag.pack(side="left", fill="both", expand=True, padx=(12, 0))

        kolonlar = [
            ("urun_adi", "Ürün Adı", 280),
            ("barkod",   "Barkod",   120),
            ("miktar",   "Miktar",    70),
            ("eklenen",  "Eklenen Depo", 130),
            ("durum",    "Durum",    320),
        ]
        self.tv = ttk.Treeview(
            sag, columns=[c[0] for c in kolonlar],
            show="headings", height=22,
        )
        for k, lbl, w in kolonlar:
            self.tv.heading(k, text=lbl)
            anchor = "w" if k in ("urun_adi", "durum") else "center"
            self.tv.column(k, width=w, anchor=anchor)

        ysb = ttk.Scrollbar(sag, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=ysb.set)
        ysb.pack(side="right", fill="y")
        self.tv.pack(side="left", fill="both", expand=True)

        self.tv.tag_configure("eklendi", background="#E8F5E9")
        self.tv.tag_configure("calisiyor", background="#FFF8E1")
        self.tv.tag_configure("hata", background="#FFEBEE")
        self.tv.tag_configure("bekliyor", background="white")

        # Log paneli
        log_frame = tk.LabelFrame(self.root, text="Log", padx=8, pady=4)
        log_frame.pack(fill="x", side="bottom", padx=12, pady=(0, 8))
        self.log_txt = tk.Text(log_frame, height=7, font=("Consolas", 8), wrap="word")
        log_sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=log_sb.set, state="disabled")
        log_sb.pack(side="right", fill="y")
        self.log_txt.pack(side="left", fill="both", expand=True)

        # Durum çubuğu
        self.lbl_durum = tk.Label(
            self.root, text="Hazır",
            font=("Arial", 9), anchor="w",
            bg="#ECEFF1", padx=12, pady=4,
        )
        self.lbl_durum.pack(fill="x", side="bottom")

    # ─────────────────────────────────────────────────────────────────────
    # Depo sıralama UI
    # ─────────────────────────────────────────────────────────────────────
    def _depo_listbox_doldur(self):
        self.lst_depo.delete(0, "end")
        for i, dk in enumerate(self.depo_sirasi, start=1):
            self.lst_depo.insert("end", f"{i}.  {DEPO_GORUNEN_AD.get(dk, dk)}")
        if self.depo_sirasi:
            self.lst_depo.selection_set(0)
        self.lbl_depo_bilgi.config(
            text=f"{len(self.depo_sirasi)} aktif depo (login bilgisi tam olanlar)."
        )

    def _depo_yukari(self):
        sel = self.lst_depo.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.depo_sirasi[i - 1], self.depo_sirasi[i] = self.depo_sirasi[i], self.depo_sirasi[i - 1]
        self._depo_listbox_doldur()
        self.lst_depo.selection_set(i - 1)

    def _depo_asagi(self):
        sel = self.lst_depo.curselection()
        if not sel or sel[0] >= len(self.depo_sirasi) - 1:
            return
        i = sel[0]
        self.depo_sirasi[i + 1], self.depo_sirasi[i] = self.depo_sirasi[i], self.depo_sirasi[i + 1]
        self._depo_listbox_doldur()
        self.lst_depo.selection_set(i + 1)

    def _depo_sirasi_resetle(self):
        self.depo_sirasi = [
            d for d in _env_depo_siralamasi()
            if _depo_kullanilabilir_mi(d, self.credentials)
        ]
        self._depo_listbox_doldur()
        self._log("Depo sırası .env değerine sıfırlandı.")

    # ─────────────────────────────────────────────────────────────────────
    # Log + durum
    # ─────────────────────────────────────────────────────────────────────
    def _log(self, msg: str):
        try:
            self.log_txt.configure(state="normal")
            self.log_txt.insert("end", msg + "\n")
            self.log_txt.see("end")
            self.log_txt.configure(state="disabled")
        except Exception:
            pass
        logger.info(msg)

    def _log_safe(self, msg: str):
        self.root.after(0, lambda m=msg: self._log(m))

    def _durum(self, msg: str):
        try:
            self.lbl_durum.config(text=msg)
            self.root.update_idletasks()
        except Exception:
            pass

    def _durum_safe(self, msg: str):
        self.root.after(0, lambda m=msg: self._durum(m))

    # ─────────────────────────────────────────────────────────────────────
    # Sipariş DB'den aktif çalışma
    # ─────────────────────────────────────────────────────────────────────
    def _aktif_calismayi_yukle(self):
        try:
            from siparis_db import get_siparis_db
            sdb = get_siparis_db()
            self.aktif_calisma = sdb.aktif_calisma_getir()
        except Exception as e:
            messagebox.showerror("Hata", f"Sipariş DB açılamadı:\n{e}", parent=self.root)
            return

        if not self.aktif_calisma:
            self.lbl_calisma.config(text="⚠  Aktif sipariş çalışması yok")
            self.lbl_ist.config(text="Önce Sipariş Verme modülünde liste oluşturun.")
            self._log("Aktif sipariş çalışması bulunamadı.")
            return

        try:
            self.siparisler = sdb.calisma_siparisleri_getir(self.aktif_calisma["id"])
        except Exception as e:
            messagebox.showerror("Hata", f"Siparişler getirilemedi:\n{e}", parent=self.root)
            return

        self.lbl_calisma.config(
            text=f"📋  {self.aktif_calisma['ad']}  (#{self.aktif_calisma['id']})"
        )
        self.lbl_ist.config(text=f"{len(self.siparisler)} kalem")
        self._log(f"Aktif çalışma yüklendi: {len(self.siparisler)} kalem")

        self._treeview_doldur()

    def _treeview_doldur(self):
        for iid in self.tv.get_children():
            self.tv.delete(iid)
        for s in self.siparisler:
            self.tv.insert(
                "", "end",
                iid=str(s.get("id", "")),
                values=[
                    s.get("urun_adi", ""),
                    s.get("barkod", ""),
                    s.get("miktar", 0),
                    "—",
                    "Bekliyor",
                ],
                tags=("bekliyor",),
            )

    def _tv_satir_guncelle(self, sid, eklenen: str, durum: str, tag: str):
        iid = str(sid)
        if self.tv.exists(iid):
            mevcut = self.tv.item(iid, "values")
            self.tv.item(iid, values=[mevcut[0], mevcut[1], mevcut[2], eklenen, durum], tags=(tag,))

    # ─────────────────────────────────────────────────────────────────────
    # Depoları aç
    # ─────────────────────────────────────────────────────────────────────
    def _depolari_ac(self):
        if not self.siparisler:
            messagebox.showwarning(
                "Liste Boş",
                "Aktif çalışmada sipariş yok. Önce Sipariş Verme modülünde liste hazırlayın.",
                parent=self.root,
            )
            return
        if not self.depo_sirasi:
            messagebox.showwarning(
                "Depo Yok",
                "Hiçbir depo için login bilgisi tanımlı değil.\n"
                "Fatih Siparişçi'nin Ayarlar penceresinden depo bilgilerini girin.",
                parent=self.root,
            )
            return

        os.environ["BROWSER_MODE"] = self.var_mode.get()

        self.btn_depo_ac.config(state="disabled")
        self.btn_iptal.config(state="normal")
        self._durum("Depolar açılıyor — pencereleri kapatmayın...")

        def worker():
            try:
                from src.controller import MainController
                if self.controller is None:
                    self.controller = MainController(gui_window=None)

                self._log_safe("Depo girişleri yapılıyor...")
                self.controller._init_depolar(self.credentials)

                aktif = self.controller.active_depolar or {}
                self._log_safe(f"✓ {len(aktif)} depo aktif: {', '.join(aktif.keys())}")

                # Aktif depo sırası: kullanıcının seçtiği sırada AMA sadece açılabilenler
                self.depo_sirasi = [d for d in self.depo_sirasi if d in aktif]
                self.root.after(0, self._depo_listbox_doldur)

                self.root.after(0, lambda: self.btn_gonder.config(state="normal"))
                self.root.after(0, lambda: self._durum(f"✓ {len(aktif)} depo hazır — 'Sepete Gönder' butonuna basın"))
            except Exception as e:
                logger.exception("Depo açma hatası")
                self.root.after(0, lambda: messagebox.showerror(
                    "Depo Açma Hatası",
                    f"Depolar açılamadı:\n\n{e}\n\n"
                    f".env: {SIPARISCI_ENV}",
                    parent=self.root,
                ))
                self.root.after(0, lambda: self._durum("Depo açılamadı"))
            finally:
                self.root.after(0, lambda: self.btn_depo_ac.config(state="normal"))
                self.root.after(0, lambda: self.btn_iptal.config(state="disabled"))

        threading.Thread(target=worker, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────
    # Kademeli sepete gönderme
    # ─────────────────────────────────────────────────────────────────────
    def _sepete_gonder_baslat(self):
        if not self.controller or not self.controller.active_depolar:
            messagebox.showwarning(
                "Depolar Açık Değil",
                "Önce 'Depoları Aç & Giriş Yap' butonuna basın.",
                parent=self.root,
            )
            return
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("İşlem Sürüyor", "Mevcut işlem bitsin.", parent=self.root)
            return
        if not self.siparisler:
            messagebox.showinfo("Liste Boş", "Sipariş listesi boş.", parent=self.root)
            return

        # Onay
        sira_metni = " → ".join(DEPO_GORUNEN_AD.get(d, d) for d in self.depo_sirasi)
        if not messagebox.askyesno(
            "Sepete Gönder",
            f"{len(self.siparisler)} kalem sırasıyla şu depolara denenecek:\n\n"
            f"{sira_metni}\n\n"
            "Bir depoya eklenebilen ürünler sonraki depolarda atlanır.\n"
            "Devam edilsin mi?",
            parent=self.root,
        ):
            return

        # Treeview sıfırla
        for s in self.siparisler:
            self._tv_satir_guncelle(s["id"], "—", "Bekliyor", "bekliyor")

        self.iptal_istendi = False
        self.btn_gonder.config(state="disabled")
        self.btn_depo_ac.config(state="disabled")
        self.btn_iptal.config(state="normal")
        self._durum("Sepete gönderme başladı...")

        def worker():
            try:
                rapor = self._sepete_gonder_yap()
                self.root.after(0, lambda r=rapor: self._sepete_gonder_bitti(r))
            except Exception as e:
                logger.exception("Sepete gönderme hatası")
                self.root.after(0, lambda: messagebox.showerror(
                    "Hata", f"Sepete gönderme sırasında hata:\n{e}", parent=self.root,
                ))
                self.root.after(0, self._sepete_gonder_temizle)

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _sepete_gonder_yap(self) -> dict:
        """
        Kademeli akış:
        - kalanlar = tüm satırlar
        - her depo için: kalanlar üzerinden geç, başarılı olanlar listeden düşer
        Returns:
            dict — { depo_key: [eklenen_satirlar], "_hicbirinde": [...] }
        """
        rapor = {dk: [] for dk in self.depo_sirasi}
        rapor["_hicbirinde"] = []

        kalanlar = list(self.siparisler)
        toplam = len(self.siparisler)

        for depo_key in self.depo_sirasi:
            if self.iptal_istendi or not kalanlar:
                break

            depo = self.controller.active_depolar.get(depo_key)
            if not depo:
                self._log_safe(f"⚠ {depo_key} aktif değil, atlanıyor")
                continue

            depo_adi = DEPO_GORUNEN_AD.get(depo_key, depo_key)
            self._log_safe(f"")
            self._log_safe(f"═══ {depo_adi} — {len(kalanlar)} kalem deneniyor ═══")
            self._durum_safe(f"{depo_adi}: 0/{len(kalanlar)}")

            # Bu depo için ekleyebildiklerimiz
            eklendi_idler = set()

            for i, s in enumerate(kalanlar, start=1):
                if self.iptal_istendi:
                    break

                barkod = (s.get("barkod") or "").strip()
                miktar = int(s.get("miktar") or 0)
                urun_adi = s.get("urun_adi", "")[:50]
                sid = s["id"]

                if not barkod or miktar <= 0:
                    self._log_safe(f"  [{i}] {urun_adi} → barkod/miktar boş, atlandı")
                    self.root.after(0, lambda sid=sid: self._tv_satir_guncelle(
                        sid, "—", "Barkod/miktar boş", "hata"
                    ))
                    # Bu satır kalanlar listesinden de çıkarılsın (hata olarak işaretle)
                    eklendi_idler.add(sid)  # kademeden çıkar
                    rapor["_hicbirinde"].append(s)
                    continue

                self._durum_safe(f"{depo_adi}: {i}/{len(kalanlar)} — {urun_adi[:40]}")
                self.root.after(0, lambda sid=sid, da=depo_adi: self._tv_satir_guncelle(
                    sid, da + " ...", "Aranıyor", "calisiyor"
                ))

                try:
                    # Tab'a geç (paralel modda gerekli)
                    depo.switch_to_tab()
                    bulundu = depo.search_barcode(barkod)
                except Exception as e:
                    self._log_safe(f"  [{i}] {urun_adi} → arama hatası: {e}")
                    self.root.after(0, lambda sid=sid: self._tv_satir_guncelle(
                        sid, "—", f"Arama hatası", "hata"
                    ))
                    continue  # sonraki depoda denenecek

                if not bulundu:
                    self._log_safe(f"  [{i}] {urun_adi} → barkod bulunamadı, sonraki depo")
                    self.root.after(0, lambda sid=sid, da=depo_adi: self._tv_satir_guncelle(
                        sid, "—", f"{da}: barkod yok → sonraki depo", "bekliyor"
                    ))
                    continue  # bu satır sonraki depoda denenecek

                try:
                    eklendi = depo.add_to_cart(miktar, secenek=None)
                except Exception as e:
                    self._log_safe(f"  [{i}] {urun_adi} → sepete ekleme hatası: {e}")
                    self.root.after(0, lambda sid=sid: self._tv_satir_guncelle(
                        sid, "—", "Sepete eklenemedi (hata)", "hata"
                    ))
                    continue

                if eklendi:
                    self._log_safe(f"  [{i}] ✓ {urun_adi} → {depo_adi} ({miktar} adet)")
                    self.root.after(0, lambda sid=sid, da=depo_adi, m=miktar: self._tv_satir_guncelle(
                        sid, da, f"✓ {m} adet sepete eklendi", "eklendi"
                    ))
                    eklendi_idler.add(sid)
                    rapor[depo_key].append(s)
                else:
                    self._log_safe(f"  [{i}] ✗ {urun_adi} → {depo_adi}: sepete eklenemedi, sonraki depo")
                    self.root.after(0, lambda sid=sid, da=depo_adi: self._tv_satir_guncelle(
                        sid, "—", f"{da}: sepete eklenemedi → sonraki depo", "bekliyor"
                    ))

            # Bu depoda eklenenleri kalanlar listesinden düş
            kalanlar = [s for s in kalanlar if s["id"] not in eklendi_idler]
            self._log_safe(
                f"═══ {depo_adi} bitti — {len(eklendi_idler)} eklendi, "
                f"{len(kalanlar)} kalemler sonraki depoya iniyor ═══"
            )

        # Hiçbir depoya eklenmeyenler
        eklendi_tum = set()
        for dk in self.depo_sirasi:
            for s in rapor.get(dk, []):
                eklendi_tum.add(s["id"])
        for s in self.siparisler:
            if s["id"] not in eklendi_tum and s not in rapor["_hicbirinde"]:
                rapor["_hicbirinde"].append(s)
                self.root.after(0, lambda sid=s["id"]: self._tv_satir_guncelle(
                    sid, "—", "❌ Hiçbir depoda eklenemedi", "hata"
                ))

        rapor["_toplam"] = toplam
        return rapor

    def _sepete_gonder_bitti(self, rapor: dict):
        self._sepete_gonder_temizle()

        toplam = rapor.get("_toplam", 0)
        hicbirinde = rapor.get("_hicbirinde", [])
        eklenen_sayisi = toplam - len(hicbirinde)

        if self.iptal_istendi:
            self._durum(f"İptal edildi — {eklenen_sayisi}/{toplam} eklendi")
        else:
            self._durum(f"Tamamlandı — {eklenen_sayisi}/{toplam} eklendi")

        # Özet rapor
        satirlar = [f"TOPLAM {toplam} kalem işlendi.\n"]
        for dk in self.depo_sirasi:
            sayi = len(rapor.get(dk, []))
            if sayi > 0:
                satirlar.append(f"  • {DEPO_GORUNEN_AD.get(dk, dk)}: {sayi} kalem eklendi")
        if hicbirinde:
            satirlar.append(f"\n❌ Hiçbir depoya eklenemeyen {len(hicbirinde)} kalem:")
            for s in hicbirinde[:20]:
                satirlar.append(f"  · {s.get('urun_adi', '?')[:50]}  ({s.get('barkod', '')})")
            if len(hicbirinde) > 20:
                satirlar.append(f"  ... ve {len(hicbirinde) - 20} kalem daha (Treeview'da kırmızı)")

        ozet = "\n".join(satirlar)
        for s in satirlar:
            self._log(s)

        messagebox.showinfo("Sepete Gönderme Tamamlandı", ozet, parent=self.root)

    def _sepete_gonder_temizle(self):
        self.btn_gonder.config(state="normal")
        self.btn_depo_ac.config(state="normal")
        self.btn_iptal.config(state="disabled")

    # ─────────────────────────────────────────────────────────────────────
    # İptal
    # ─────────────────────────────────────────────────────────────────────
    def _iptal_et(self):
        self.iptal_istendi = True
        self._log("İptal istendi — mevcut adım bitince duracak...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    root.geometry("1400x800")
    HibritSiparisciGUI(root)
    root.mainloop()
