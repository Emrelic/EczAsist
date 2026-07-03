"""
Hasta İşlem Süresi Takip Modülü — Arayüz

İki parça:
  1) KronometrePenceresi : Ekranın sağ altına yapışan, HER ZAMAN ÜSTTE duran,
     küçücük bir kronometre. Butonlar: Başlat · Durdur/Sürdür · Ekle · Bitir.
     Bir hasta gelince Başlat'a basılır, gerekirse Durdur/Sürdür ile duraklatılır.
     Bitir işlemi kaydeder. Hasta kapıdan çıkmadan dönüp bir şey sorarsa "Ekle"
     ile aynı işleme süre eklenip tekrar Bitir'e basılır (aynı kayıt güncellenir).

  2) HastaSureGUI : Ana menüden açılan modül ekranı. "İstatistik Topla"
     checkbox'ı işaretlenince küçük sayaç penceresi sağ altta belirir.
     İstatistikleri (bugün adedi/ortalama/en uzun-kısa, son işlemler, personel,
     son 7 gün, saatlik yoğunluk) gösterir.

Botanik EOS'a ASLA bağlanmaz/yazmaz — tamamen yerel (hasta_sure_takip.db).
"""

import os
import json
import time
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from hasta_sure_db import HastaSureDB, sure_bicimle

try:
    from tema_yonetimi import get_tema
except Exception:
    get_tema = None

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_AYAR_DOSYA = os.path.join(_SCRIPT_DIR, "hasta_sure_ayar.json")


def _renkler():
    """Aktif tema renklerini getir (tema modülü yoksa makul varsayılan)."""
    if get_tema is not None:
        try:
            return get_tema().renkler
        except Exception:
            pass
    return {
        "bg": "#1E1E1E", "bg_secondary": "#2D2D2D", "card_bg": "#2D2D2D",
        "input_bg": "#3D3D3D", "input_fg": "#FFFFFF",
        "fg": "#FFFFFF", "fg_secondary": "#B0B0B0", "fg_muted": "#707070",
        "accent": "#1976D2", "success": "#4CAF50", "warning": "#FF9800",
        "error": "#F44336", "info": "#2196F3", "border": "#404040",
        "frame_bg": "#252525", "frame_fg": "#90CAF9",
    }


def _ayar_yukle():
    try:
        if os.path.exists(_AYAR_DOSYA):
            with open(_AYAR_DOSYA, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _ayar_kaydet(ayar):
    try:
        with open(_AYAR_DOSYA, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Hasta süre ayarı kaydedilemedi: %s", e)


# ═══════════════════════════════════════════════════════════════════════════
# KÜÇÜK YÜZEN KRONOMETRE PENCERESİ
# ═══════════════════════════════════════════════════════════════════════════
class KronometrePenceresi:
    """Sağ alta yapışan, her zaman üstte, küçük kronometre penceresi."""

    def __init__(self, master, db, personel="", on_kayit=None, on_kapat=None):
        self.master = master
        self.db = db
        self.personel = personel or ""
        self.on_kayit = on_kayit          # kayıt sonrası (istatistik tazele)
        self.on_kapat = on_kapat          # pencere kapanınca (checkbox'ı kaldır)

        # ---- durum makinesi ----
        # bos -> calisiyor <-> durakladi -> bitti -> (Ekle) calisiyor / (Yeni) calisiyor
        self.durum = "bos"
        self._biriken = 0.0               # biten segmentlerden toplanan saniye
        self._segment_baslangic = None    # monotonic() — aktif segment başlangıcı
        self._ilk_baslangic_dt = None     # ilk "Başlat" datetime'ı
        self._kayit_id = None             # DB'ye yazılmış kaydın id'si
        self._ekleme_say = 0
        self._tik_job = None

        self.r = _renkler()
        self._pencere_kur()
        self._durum_uygula()

    # -------------------------------------------------------------- pencere
    def _pencere_kur(self):
        r = self.r
        yesil = "#2E7D32"          # pencere arkaplanı (yeşil)
        yesil_ac = "#C8E6C9"       # yeşil üstünde soluk metin
        self.win = tk.Toplevel(self.master)
        self.win.title("⏱ Hasta Süre")
        self.win.configure(bg=yesil)
        self.win.resizable(False, False)
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        self.win.protocol("WM_DELETE_WINDOW", self.kapat)

        dis = tk.Frame(self.win, bg=yesil, padx=5, pady=3)
        dis.pack(fill="both", expand=True)

        # --- Ad soyad (opsiyonel) ---
        ust = tk.Frame(dis, bg=yesil)
        ust.pack(fill="x")
        tk.Label(ust, text="👤", bg=yesil, fg=yesil_ac,
                 font=("Segoe UI", 8)).pack(side="left")
        self.ad_var = tk.StringVar()
        self.ad_entry = tk.Entry(
            ust, textvariable=self.ad_var, bg=r["input_bg"], fg=r["input_fg"],
            insertbackground=r["fg"], relief="flat", font=("Segoe UI", 8),
            width=14)
        self.ad_entry.pack(side="left", fill="x", expand=True, padx=(3, 0))
        # placeholder benzeri ipucu
        self._ipucu_kur(self.ad_entry, self.ad_var, "Ad Soyad (ops.)")

        # --- Süre göstergesi (rakamlar beyaz) ---
        self.sure_lbl = tk.Label(
            dis, text="00:00", bg=yesil, fg="#FFFFFF",
            font=("Consolas", 20, "bold"))
        self.sure_lbl.pack(pady=(1, 1))

        # --- Butonlar: [Başlat/Durdur/Sürdür] [Ekle] [Bitir/Yeni] ---
        # Durdur↔Sürdür ve ayrıca Bitir↔Yeni aynı butonda dönüşümlü.
        btn_fr = tk.Frame(dis, bg=yesil)
        btn_fr.pack(fill="x")

        def mk(parent, text, cmd, renk):
            b = tk.Button(parent, text=text, command=cmd, bg=renk, fg="#FFFFFF",
                          activebackground=renk, activeforeground="#FFFFFF",
                          relief="flat", font=("Segoe UI", 8, "bold"),
                          disabledforeground="#DDDDDD", cursor="hand2",
                          padx=2, pady=1)
            b.pack(side="left", expand=True, fill="x", padx=1)
            return b

        self.btn_ana = mk(btn_fr, "▶ Başlat", self.ana_dugme, r["success"])
        self.btn_ekle = mk(btn_fr, "➕ Ekle", self.ekle, r["info"])
        self.btn_bitir = mk(btn_fr, "⏹ Bitir", self.bitir_yeni, r["error"])

        # --- Bir önceki kaydı sil (küçük, ikincil satır) ---
        self.btn_son_sil = tk.Button(
            dis, text="↩ Bir Önceki Kaydı Sil", command=self.son_kaydi_sil,
            bg=yesil, fg=yesil_ac, activebackground=yesil,
            activeforeground="#FFFFFF", relief="flat", bd=0,
            font=("Segoe UI", 7, "underline"), cursor="hand2")
        self.btn_son_sil.pack(fill="x", pady=(2, 0))

        # sağ alta yerleştir
        self.win.update_idletasks()
        w = self.win.winfo_width() or 200
        h = self.win.winfo_height() or 100
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = sw - w - 20
        y = sh - h - 60           # görev çubuğunun biraz üstü
        self.win.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _ipucu_kur(self, entry, var, ipucu):
        """Basit placeholder davranışı."""
        r = self.r

        def _bos_goster():
            if not var.get():
                entry.config(fg=r["fg_muted"])
                entry.insert(0, ipucu)
                entry._ipucu_aktif = True

        def _focus_in(_e):
            if getattr(entry, "_ipucu_aktif", False):
                entry.delete(0, "end")
                entry.config(fg=r["input_fg"])
                entry._ipucu_aktif = False

        def _focus_out(_e):
            if not entry.get():
                _bos_goster()

        entry._ipucu_aktif = False
        _bos_goster()
        entry.bind("<FocusIn>", _focus_in)
        entry.bind("<FocusOut>", _focus_out)

    def _ad_oku(self):
        """Placeholder'ı hesaba katarak gerçek ad değerini oku."""
        if getattr(self.ad_entry, "_ipucu_aktif", False):
            return ""
        return self.ad_var.get().strip()

    def _ad_temizle(self):
        self.ad_entry.delete(0, "end")
        self.ad_entry._ipucu_aktif = False
        self.ad_entry.event_generate("<FocusOut>")

    # -------------------------------------------------------------- süre
    def _gecen(self):
        t = self._biriken
        if self.durum == "calisiyor" and self._segment_baslangic is not None:
            t += time.monotonic() - self._segment_baslangic
        return t

    def _tik(self):
        self.sure_lbl.config(text=sure_bicimle(self._gecen()))
        if self.durum == "calisiyor":
            self._tik_job = self.win.after(250, self._tik)
        else:
            self._tik_job = None

    def _tik_baslat(self):
        if self._tik_job is None:
            self._tik()

    def _tik_durdur(self):
        if self._tik_job is not None:
            try:
                self.win.after_cancel(self._tik_job)
            except Exception:
                pass
            self._tik_job = None
        self.sure_lbl.config(text=sure_bicimle(self._gecen()))

    # -------------------------------------------------------------- eylemler
    def ana_dugme(self):
        """Sol buton: duruma göre Başlat / Durdur / Sürdür."""
        if self.durum == "bos":
            self.baslat()
        elif self.durum in ("calisiyor", "durakladi"):
            self.durdur_surdur()

    def bitir_yeni(self):
        """Sağ buton: Bitir ↔ Yeni dönüşümlü."""
        if self.durum in ("calisiyor", "durakladi"):
            self.bitir()
        elif self.durum == "bitti":
            self.baslat()          # yeni hasta

    def baslat(self):
        """Yeni hasta — süreyi sıfırdan başlat (bos ya da bitti durumundan)."""
        if self.durum == "bitti":
            self._ad_temizle()           # yeni hasta için alanı temizle
        self._biriken = 0.0
        self._ekleme_say = 0
        self._kayit_id = None
        self._ilk_baslangic_dt = datetime.now()
        self._segment_baslangic = time.monotonic()
        self.durum = "calisiyor"
        self._durum_uygula()
        self._tik_baslat()

    def durdur_surdur(self):
        if self.durum == "calisiyor":
            self._biriken += time.monotonic() - self._segment_baslangic
            self._segment_baslangic = None
            self.durum = "durakladi"
            self._tik_durdur()
        elif self.durum == "durakladi":
            self._segment_baslangic = time.monotonic()
            self.durum = "calisiyor"
            self._tik_baslat()
        self._durum_uygula()

    def ekle(self):
        """Bitmiş işleme geri dön ve süre eklemeye devam et (aynı kayıt)."""
        if self.durum != "bitti":
            return
        self._segment_baslangic = time.monotonic()
        self._ekleme_say += 1
        self.durum = "calisiyor"
        self._durum_uygula()
        self._tik_baslat()

    def bitir(self):
        """İşlemi bitir ve kaydet/güncelle."""
        if self.durum == "calisiyor":
            self._biriken += time.monotonic() - self._segment_baslangic
            self._segment_baslangic = None
        elif self.durum not in ("durakladi",):
            return
        self._tik_durdur()
        sure = self._gecen()
        bitis = datetime.now()
        try:
            if self._kayit_id is None:
                self._kayit_id = self.db.islem_kaydet(
                    hasta_adi=self._ad_oku(), personel=self.personel,
                    baslangic_dt=self._ilk_baslangic_dt, bitis_dt=bitis,
                    sure_saniye=sure, ekleme_say=self._ekleme_say,
                    notu="")
            else:
                self.db.islem_guncelle(
                    self._kayit_id, bitis_dt=bitis, sure_saniye=sure,
                    ekleme_say=self._ekleme_say, hasta_adi=self._ad_oku())
        except Exception as e:
            logger.error("İşlem kaydı hatası: %s", e, exc_info=True)
            messagebox.showerror("Hata", f"Kayıt yapılamadı:\n{e}",
                                 parent=self.win)
            return
        self.durum = "bitti"
        self._durum_uygula()
        if self.on_kayit:
            try:
                self.on_kayit()
            except Exception:
                pass

    # -------------------------------------------------------------- görünüm
    def _durum_uygula(self):
        """Duruma göre 3 buton: aktif/pasif + etiket + renk."""
        r = self.r
        d = self.durum
        pasif = r["bg_secondary"]

        # Sol buton (Başlat / Durdur / Sürdür)
        if d == "bos":
            ana = ("normal", "▶ Başlat", r["success"])
        elif d == "calisiyor":
            ana = ("normal", "⏸ Durdur", r["warning"])
        elif d == "durakladi":
            ana = ("normal", "▶ Sürdür", r["success"])
        else:  # bitti
            ana = ("disabled", "▶ Başlat", pasif)

        # Ekle butonu (yalnız bitti)
        ekle = ("normal", r["info"]) if d == "bitti" else ("disabled", pasif)

        # Sağ buton (Bitir ↔ Yeni)
        if d in ("calisiyor", "durakladi"):
            bitir = ("normal", "⏹ Bitir", r["error"])
        elif d == "bitti":
            bitir = ("normal", "🔄 Yeni", r["success"])
        else:  # bos
            bitir = ("disabled", "⏹ Bitir", pasif)

        self.btn_ana.config(state=ana[0], text=ana[1], bg=ana[2],
                            activebackground=ana[2])
        self.btn_ekle.config(state=ekle[0], bg=ekle[1], activebackground=ekle[1])
        self.btn_bitir.config(state=bitir[0], text=bitir[1], bg=bitir[2],
                             activebackground=bitir[2])
        # Not: süre rakamları her durumda beyaz kalır (fg değiştirilmez).

    def son_kaydi_sil(self):
        """En son kaydedilen işlemi (yanlış/kazara kayıt) sil."""
        try:
            son = self.db.son_kayit()
        except Exception as e:
            messagebox.showerror("Hata", f"Kayıt okunamadı:\n{e}",
                                 parent=self.win)
            return
        if not son:
            messagebox.showinfo("Bilgi", "Silinecek kayıt yok.",
                                parent=self.win)
            return
        ad = son.get("hasta_adi") or "(isimsiz)"
        saat = (son.get("bitis") or son.get("baslangic") or "")[11:16]
        onay = messagebox.askyesno(
            "Bir Önceki Kaydı Sil",
            f"Son kayıt silinsin mi?\n\n"
            f"Hasta: {ad}\nSaat: {saat or '—'}\n"
            f"Süre: {sure_bicimle(son.get('sure_saniye'))}",
            parent=self.win)
        if not onay:
            return
        try:
            self.db.islem_sil(son["id"])
        except Exception as e:
            messagebox.showerror("Hata", f"Silinemedi:\n{e}", parent=self.win)
            return
        # Silinen kayıt şu anki 'bitti' oturumunun kaydıysa sayacı sıfırla
        if son["id"] == self._kayit_id:
            self._tik_durdur()
            self._biriken = 0.0
            self._segment_baslangic = None
            self._kayit_id = None
            self._ekleme_say = 0
            self.durum = "bos"
            self._ad_temizle()
            self.sure_lbl.config(text="00:00")
            self._durum_uygula()
        if self.on_kayit:
            try:
                self.on_kayit()
            except Exception:
                pass

    # -------------------------------------------------------------- kapat
    def kapat(self):
        if self.durum in ("calisiyor", "durakladi"):
            cevap = messagebox.askyesnocancel(
                "Süren işlem var",
                "Bir hasta işlemi sürüyor.\n\n"
                "Evet: kaydedip kapat\nHayır: kaydetmeden kapat\n"
                "İptal: açık kalsın",
                parent=self.win)
            if cevap is None:
                return
            if cevap:
                self.bitir()
        self._tik_durdur()
        try:
            self.win.destroy()
        except Exception:
            pass
        if self.on_kapat:
            try:
                self.on_kapat()
            except Exception:
                pass

    def one_getir(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.attributes("-topmost", True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# MODÜL EKRANI (ana menüden açılır)
# ═══════════════════════════════════════════════════════════════════════════
class HastaSureGUI:
    """Hasta işlem süresi modülü ana ekranı + istatistikler."""

    def __init__(self, parent, personel="", ana_menu_callback=None):
        self.parent = parent
        self.personel = personel or ""
        self.ana_menu_callback = ana_menu_callback
        self.db = HastaSureDB()
        self.krono = None
        self.r = _renkler()

        try:
            self.parent.title("⏱ Hasta İşlem Süresi Takibi")
        except Exception:
            pass
        self.parent.configure(bg=self.r["bg"])
        if get_tema is not None:
            try:
                get_tema().ttk_stili_uygula()
            except Exception:
                pass

        self._arayuz_kur()
        self._istatistik_tazele()

        # Pencere kapanınca kronometreyi de kapat
        try:
            self.parent.protocol("WM_DELETE_WINDOW", self._modul_kapat)
        except Exception:
            pass

        # Ayardan hatırla: istatistik topla açıksa küçük pencereyi aç
        ayar = _ayar_yukle()
        if ayar.get("istatistik_topla"):
            self.topla_var.set(True)
            self._topla_degisti()

    # -------------------------------------------------------------- arayüz
    def _arayuz_kur(self):
        r = self.r

        # Başlık
        header = tk.Frame(self.parent, bg=r["accent"], height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⏱  Hasta İşlem Süresi Takibi",
                 bg=r["accent"], fg="#FFFFFF",
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=16)
        tk.Label(header, text=f"👤 {self.personel}", bg=r["accent"],
                 fg="#E3F2FD", font=("Segoe UI", 10)).pack(side="right", padx=16)

        govde = tk.Frame(self.parent, bg=r["bg"], padx=16, pady=12)
        govde.pack(fill="both", expand=True)

        # --- Kontrol kutusu: İstatistik Topla ---
        kontrol = tk.Frame(govde, bg=r["frame_bg"], padx=14, pady=12,
                           highlightbackground=r["border"], highlightthickness=1)
        kontrol.pack(fill="x")

        self.topla_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(
            kontrol, variable=self.topla_var, command=self._topla_degisti,
            text="  📊  İstatistik Topla — küçük sayaç penceresini sağ altta göster",
            bg=r["frame_bg"], fg=r["fg"], selectcolor=r["input_bg"],
            activebackground=r["frame_bg"], activeforeground=r["fg"],
            font=("Segoe UI", 12, "bold"), cursor="hand2",
            anchor="w")
        cb.pack(side="left")

        self.durum_lbl = tk.Label(
            kontrol, text="● Kapalı", bg=r["frame_bg"], fg=r["fg_muted"],
            font=("Segoe UI", 10, "bold"))
        self.durum_lbl.pack(side="right")

        tk.Label(govde,
                 text="Küçük pencere: bir hasta gelince ▶ Başlat • gerekince "
                      "⏸ Durdur/Sürdür • hasta dönüp sorarsa ➕ Ekle • bitince "
                      "⏹ Bitir ile kaydedilir.",
                 bg=r["bg"], fg=r["fg_secondary"], font=("Segoe UI", 9),
                 anchor="w", justify="left").pack(fill="x", pady=(6, 10))

        # --- Bugün özet kartları ---
        self.ozet_fr = tk.Frame(govde, bg=r["bg"])
        self.ozet_fr.pack(fill="x", pady=(0, 10))
        self.ozet_kartlar = {}
        for anahtar, baslik in [
            ("adet", "Bugün Hasta"), ("ortalama", "Ortalama Süre"),
            ("en_uzun", "En Uzun"), ("en_kisa", "En Kısa"),
            ("toplam", "Toplam Süre")]:
            kart = tk.Frame(self.ozet_fr, bg=r["card_bg"], padx=14, pady=10,
                            highlightbackground=r["border"], highlightthickness=1)
            kart.pack(side="left", expand=True, fill="x", padx=4)
            deger = tk.Label(kart, text="—", bg=r["card_bg"], fg=r["accent"],
                             font=("Segoe UI", 18, "bold"))
            deger.pack()
            tk.Label(kart, text=baslik, bg=r["card_bg"], fg=r["fg_secondary"],
                     font=("Segoe UI", 9)).pack()
            self.ozet_kartlar[anahtar] = deger

        # --- Alt: sol son işlemler, sağ personel + 7 gün ---
        alt = tk.Frame(govde, bg=r["bg"])
        alt.pack(fill="both", expand=True)

        # Son işlemler tablosu
        sol = tk.LabelFrame(alt, text=" Bugünün İşlemleri ", bg=r["frame_bg"],
                            fg=r["frame_fg"], font=("Segoe UI", 10, "bold"),
                            padx=6, pady=6)
        sol.pack(side="left", fill="both", expand=True, padx=(0, 6))

        arac = tk.Frame(sol, bg=r["frame_bg"])
        arac.pack(fill="x", pady=(0, 4))
        tk.Button(arac, text="🔄 Yenile", command=self._istatistik_tazele,
                  bg=r["accent"], fg="#FFFFFF", relief="flat",
                  font=("Segoe UI", 9), cursor="hand2", padx=8).pack(side="left")
        tk.Button(arac, text="🗑 Seçili Kaydı Sil", command=self._kayit_sil,
                  bg=r["error"], fg="#FFFFFF", relief="flat",
                  font=("Segoe UI", 9), cursor="hand2", padx=8).pack(side="left",
                                                                     padx=6)
        tk.Button(arac, text="↩ Bir Önceki Kaydı Sil",
                  command=self._son_kaydi_sil, bg=r["warning"], fg="#FFFFFF",
                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                  padx=8).pack(side="left")

        kolonlar = ("saat", "hasta", "sure", "ekle", "personel")
        self.tablo = ttk.Treeview(sol, columns=kolonlar, show="headings",
                                  height=12)
        for k, b, g in [("saat", "Başlangıç", 90), ("hasta", "Hasta", 150),
                        ("sure", "Süre", 80), ("ekle", "Ekleme", 70),
                        ("personel", "Personel", 110)]:
            self.tablo.heading(k, text=b)
            self.tablo.column(k, width=g,
                              anchor="center" if k in ("saat", "sure", "ekle")
                              else "w")
        self.tablo.pack(fill="both", expand=True)

        # Sağ panel
        sag = tk.Frame(alt, bg=r["bg"], width=280)
        sag.pack(side="right", fill="y")
        sag.pack_propagate(False)

        per_fr = tk.LabelFrame(sag, text=" Bugün — Personel ", bg=r["frame_bg"],
                               fg=r["frame_fg"], font=("Segoe UI", 10, "bold"),
                               padx=6, pady=6)
        per_fr.pack(fill="both", expand=True, pady=(0, 6))
        self.per_tablo = ttk.Treeview(
            per_fr, columns=("personel", "adet", "ort"), show="headings",
            height=6)
        for k, b, g in [("personel", "Personel", 120), ("adet", "Adet", 55),
                        ("ort", "Ort.", 70)]:
            self.per_tablo.heading(k, text=b)
            self.per_tablo.column(k, width=g,
                                  anchor="w" if k == "personel" else "center")
        self.per_tablo.pack(fill="both", expand=True)

        gun_fr = tk.LabelFrame(sag, text=" Son 7 Gün ", bg=r["frame_bg"],
                               fg=r["frame_fg"], font=("Segoe UI", 10, "bold"),
                               padx=6, pady=6)
        gun_fr.pack(fill="both", expand=True)
        self.gun_tablo = ttk.Treeview(
            gun_fr, columns=("gun", "adet", "ort"), show="headings", height=7)
        for k, b, g in [("gun", "Gün", 100), ("adet", "Adet", 55),
                        ("ort", "Ort.", 70)]:
            self.gun_tablo.heading(k, text=b)
            self.gun_tablo.column(k, width=g,
                                  anchor="w" if k == "gun" else "center")
        self.gun_tablo.pack(fill="both", expand=True)

    # -------------------------------------------------------------- checkbox
    def _topla_degisti(self):
        r = self.r
        acik = self.topla_var.get()
        _ayar_kaydet({"istatistik_topla": bool(acik)})
        if acik:
            if self.krono is None:
                self.krono = KronometrePenceresi(
                    self.parent, self.db, personel=self.personel,
                    on_kayit=self._istatistik_tazele,
                    on_kapat=self._krono_kapandi)
            else:
                self.krono.one_getir()
            self.durum_lbl.config(text="● Açık — sayaç sağ altta", fg=r["success"])
        else:
            if self.krono is not None:
                # kapat çağrısı on_kapat -> _krono_kapandi tetikler; döngü olmasın
                k = self.krono
                self.krono = None
                k.on_kapat = None
                k.kapat()
            self.durum_lbl.config(text="● Kapalı", fg=r["fg_muted"])

    def _krono_kapandi(self):
        """Küçük pencere kendi X'i ile kapandığında checkbox'ı geri al."""
        self.krono = None
        try:
            self.topla_var.set(False)
            self.durum_lbl.config(text="● Kapalı", fg=self.r["fg_muted"])
            _ayar_kaydet({"istatistik_topla": False})
        except Exception:
            pass

    # -------------------------------------------------------------- istatistik
    def _istatistik_tazele(self):
        try:
            o = self.db.gun_ozeti()
            self.ozet_kartlar["adet"].config(text=str(o["adet"]))
            self.ozet_kartlar["ortalama"].config(text=sure_bicimle(o["ortalama"]))
            self.ozet_kartlar["en_uzun"].config(text=sure_bicimle(o["en_uzun"]))
            self.ozet_kartlar["en_kisa"].config(text=sure_bicimle(o["en_kisa"]))
            self.ozet_kartlar["toplam"].config(text=sure_bicimle(o["toplam"]))
        except Exception as e:
            logger.warning("Özet tazeleme hatası: %s", e)

        # Bugünün işlemleri
        for i in self.tablo.get_children():
            self.tablo.delete(i)
        try:
            bugun = datetime.now().strftime("%Y-%m-%d")
            for satir in self.db.son_islemler(limit=300, tarih=bugun):
                bas = (satir.get("baslangic") or "")[11:16]
                ekle = satir.get("ekleme_say") or 0
                self.tablo.insert("", "end", iid=str(satir["id"]), values=(
                    bas or "—", satir.get("hasta_adi") or "—",
                    sure_bicimle(satir.get("sure_saniye")),
                    (f"+{ekle}" if ekle else "—"),
                    satir.get("personel") or "—"))
        except Exception as e:
            logger.warning("İşlem tablosu hatası: %s", e)

        # Personel özeti
        for i in self.per_tablo.get_children():
            self.per_tablo.delete(i)
        try:
            for p in self.db.personel_ozeti():
                self.per_tablo.insert("", "end", values=(
                    p["personel"], p["adet"], sure_bicimle(p["ortalama"])))
        except Exception as e:
            logger.warning("Personel özeti hatası: %s", e)

        # Son 7 gün
        for i in self.gun_tablo.get_children():
            self.gun_tablo.delete(i)
        try:
            for g in self.db.gunluk_seri(7):
                etiket = datetime.strptime(g["tarih"], "%Y-%m-%d").strftime("%d.%m %a")
                self.gun_tablo.insert("", "end", values=(
                    etiket, g["adet"], sure_bicimle(g["ortalama"])))
        except Exception as e:
            logger.warning("Günlük seri hatası: %s", e)

    def _son_kaydi_sil(self):
        """En son kaydedilen işlemi sil (kronometre penceresi açık değilse de)."""
        try:
            son = self.db.son_kayit()
        except Exception as e:
            messagebox.showerror("Hata", f"Kayıt okunamadı:\n{e}",
                                 parent=self.parent)
            return
        if not son:
            messagebox.showinfo("Bilgi", "Silinecek kayıt yok.",
                                parent=self.parent)
            return
        ad = son.get("hasta_adi") or "(isimsiz)"
        saat = (son.get("bitis") or son.get("baslangic") or "")[11:16]
        if not messagebox.askyesno(
                "Bir Önceki Kaydı Sil",
                f"Son kayıt silinsin mi?\n\nHasta: {ad}\nSaat: {saat or '—'}\n"
                f"Süre: {sure_bicimle(son.get('sure_saniye'))}",
                parent=self.parent):
            return
        try:
            self.db.islem_sil(son["id"])
        except Exception as e:
            messagebox.showerror("Hata", f"Silinemedi:\n{e}", parent=self.parent)
            return
        # Kronometre o kaydı açık tutuyorsa sayacı da sıfırla
        if self.krono is not None and son["id"] == self.krono._kayit_id:
            self.krono._tik_durdur()
            self.krono._biriken = 0.0
            self.krono._segment_baslangic = None
            self.krono._kayit_id = None
            self.krono._ekleme_say = 0
            self.krono.durum = "bos"
            self.krono._ad_temizle()
            self.krono.sure_lbl.config(text="00:00")
            self.krono._durum_uygula()
        self._istatistik_tazele()

    def _kayit_sil(self):
        sec = self.tablo.selection()
        if not sec:
            messagebox.showinfo("Bilgi", "Silmek için bir kayıt seçin.",
                                parent=self.parent)
            return
        if not messagebox.askyesno("Onay", f"{len(sec)} kayıt silinsin mi?",
                                   parent=self.parent):
            return
        for iid in sec:
            try:
                self.db.islem_sil(int(iid))
            except Exception as e:
                logger.warning("Kayıt silme hatası (%s): %s", iid, e)
        self._istatistik_tazele()

    # -------------------------------------------------------------- kapat
    def _modul_kapat(self):
        try:
            if self.krono is not None:
                self.krono.on_kapat = None
                self.krono.kapat()
        except Exception:
            pass
        try:
            self.db.kapat()
        except Exception:
            pass
        try:
            self.parent.destroy()
        except Exception:
            pass


# Bağımsız test
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1100x680")
    HastaSureGUI(root, personel="Test Personel")
    root.mainloop()
