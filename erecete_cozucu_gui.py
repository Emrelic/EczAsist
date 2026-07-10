# -*- coding: utf-8 -*-
"""
E-Reçete No Çözücü — GUI

Okunmaz e-reçete / takip numaralarını Medula'da otomatik dener. Kullanıcı her
karakter için "kesin" değeri veya "olası" adayları girer; sistem tüm
kombinasyonları sırayla Medula'da sorgular, "bulunamadı" çıkarsa sonrakini
dener, hasta bulununca durup sonuç satırına tıklar.

🚨 Medula'da yalnızca sorgu (okuma/navigasyon) yapar — reçete verisi değiştirmez.
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from erecete_karisma_tablosu import KarismaTablosu, get_tablo
from erecete_cozucu_motor import CozucuMotor, Pozisyon
import erecete_cozucu_medula as medula
import tc_yardimci
from erecete_prefix_ogrenme import get_ogrenme

logger = logging.getLogger(__name__)

KUTU_SAYISI = 8          # Geleceğe dönük 8 kutu (şu an e-reçete/takip = 7)
VARSAYILAN_UZUNLUK = 7
UYARI_ESIGI = 300        # Bu sayının üstünde onay iste
BELIRSIZ_LIMIT = 3       # Ardışık bu kadar BELİRSİZ sonuçta dur


def _renkler():
    """Aktif tema renklerini (fallback ile) döndürür."""
    try:
        from tema_yonetimi import get_tema
        return dict(get_tema().renkler)
    except Exception:
        return {
            "bg": "#1E3A5F", "header_bg": "#0D2137", "card_bg": "#2C4A6E",
            "fg": "#FFFFFF", "fg_secondary": "#87CEEB", "border": "#3D5A80",
            "success": "#4CAF50", "warning": "#FF9800", "error": "#F44336",
        }


def _hasta_sec_popup(parent, sonuclar, on_sec):
    """Birden çok hasta eşleşmesinde seçim penceresi. on_sec(tc, ad) çağrılır."""
    r = _renkler()
    top = tk.Toplevel(parent)
    top.title("Hasta seç")
    try:
        top.attributes("-topmost", True)
        top.geometry("320x240")
    except Exception:
        pass
    top.configure(bg=r["bg"])
    tk.Label(top, text=f"{len(sonuclar)} eşleşme — birini seçin:", bg=r["bg"],
             fg=r["fg"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
    lb = tk.Listbox(top, font=("Consolas", 10), bg="#0D1B2A", fg="#D0E0F0",
                    activestyle="none")
    lb.pack(fill="both", expand=True, padx=8)
    for s in sonuclar:
        lb.insert("end", f"{s['ad']}  ·  {s['tc']}")

    def sec(_evt=None):
        i = lb.curselection()
        if i:
            s = sonuclar[i[0]]
            on_sec(s["tc"], s["ad"])
            top.destroy()

    lb.bind("<Double-Button-1>", sec)
    tk.Button(top, text="Seç", command=sec, bg=r["success"], fg="white",
              relief="flat", font=("Segoe UI", 10, "bold"),
              cursor="hand2").pack(fill="x", padx=8, pady=8)
    return top


class HastaAutocomplete:
    """Bir Entry'ye takılan canlı öneri (açılır) listesi.

    İsim yazıldıkça (debounce'lu, arka planda) `ara_fn(kelime)` çağrılır ve
    dönen {ad, tc, adet} listesi Entry'nin altında bir açılır listede gösterilir
    (eczaneye en çok gelen hasta üstte — sıralama ara_fn'e ait). Seçilince
    `on_sec(tc, ad)` çağrılır. ↑/↓ ile gezinme, Enter ile seçme, Esc ile kapatma.
    """

    def __init__(self, win, entry, ara_fn, on_sec, on_enter_bos=None,
                 gecikme_ms=280):
        self.win = win
        self.entry = entry
        self.ara_fn = ara_fn
        self.on_sec = on_sec
        self.on_enter_bos = on_enter_bos
        self.gecikme_ms = gecikme_ms
        self.pop = None
        self.lb = None
        self._after_id = None
        self._sonuclar = []
        self._son_kelime = ""
        entry.bind("<Down>", self._down, add="+")
        entry.bind("<Up>", self._up, add="+")
        entry.bind("<Escape>", lambda e: self.gizle(), add="+")
        entry.bind("<Return>", self._enter, add="+")
        entry.bind("<FocusOut>", self._focus_out, add="+")

    # ── Tetikleme / arama ─────────────────────────────────────────────
    def tetikle(self, kelime):
        self._son_kelime = kelime
        if self._after_id:
            try:
                self.entry.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.entry.after(
            self.gecikme_ms, lambda: self._ara(kelime))

    def _ara(self, kelime):
        def isle():
            try:
                r = self.ara_fn(kelime)
            except Exception:
                r = []
            try:
                self.win.after(0, lambda: self._goster(kelime, r))
            except Exception:
                pass
        threading.Thread(target=isle, daemon=True).start()

    def _goster(self, kelime, sonuclar):
        if kelime != self._son_kelime:
            return  # kullanıcı yazmaya devam etti, eski sonuç
        self._sonuclar = sonuclar
        if not sonuclar:
            self.gizle()
            return
        if self.pop is None or not self.pop.winfo_exists():
            self._pop_olustur()
        self.lb.delete(0, "end")
        for s in sonuclar:
            adet = s.get("adet")
            etk = s.get("ad", "")
            if adet:
                etk = f"{etk}   ({adet})"
            self.lb.insert("end", etk)
        self._konumla()
        try:
            self.pop.deiconify()
            self.pop.lift()
        except Exception:
            pass

    def _pop_olustur(self):
        r = _renkler()
        self.pop = tk.Toplevel(self.win)
        self.pop.overrideredirect(True)
        try:
            self.pop.attributes("-topmost", True)
        except Exception:
            pass
        self.lb = tk.Listbox(self.pop, font=("Consolas", 10), bg="#0D1B2A",
                             fg="#D0E0F0", activestyle="none", height=8,
                             highlightthickness=1, highlightbackground=r["border"],
                             selectbackground=r["success"], selectforeground="white")
        self.lb.pack(fill="both", expand=True)
        self.lb.bind("<ButtonRelease-1>", self._lb_sec)
        self.lb.bind("<Return>", self._lb_sec)

    def _konumla(self):
        try:
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            w = max(240, self.entry.winfo_width())
            yuk = min(8, len(self._sonuclar)) * 18 + 6
            self.pop.geometry(f"{w}x{yuk}+{x}+{y}")
        except Exception:
            pass

    # ── Seçim / gezinme ───────────────────────────────────────────────
    def _sec_index(self, i):
        if 0 <= i < len(self._sonuclar):
            s = self._sonuclar[i]
            self.gizle()
            self.on_sec(s.get("tc", ""), s.get("ad", ""))

    def _lb_sec(self, _e=None):
        sel = self.lb.curselection()
        if sel:
            self._sec_index(sel[0])

    def _acik(self):
        return self.pop is not None and self.pop.winfo_exists() and \
            self.pop.state() != "withdrawn"

    def _down(self, _e=None):
        if not self._acik():
            return
        cur = self.lb.curselection()
        i = (cur[0] + 1) if cur else 0
        i = min(i, self.lb.size() - 1)
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.see(i)
        return "break"

    def _up(self, _e=None):
        if not self._acik():
            return
        cur = self.lb.curselection()
        i = (cur[0] - 1) if cur else 0
        i = max(i, 0)
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.see(i)
        return "break"

    def _enter(self, _e=None):
        if self._acik():
            sel = self.lb.curselection()
            if sel:
                self._sec_index(sel[0])
                return "break"
            if self._sonuclar:
                self._sec_index(0)
                return "break"
        if self.on_enter_bos:
            self.on_enter_bos()
            return "break"

    def _focus_out(self, _e=None):
        # Listbox tıklamasının kaydedilmesine izin vermek için gecikmeli gizle
        self.entry.after(200, self.gizle)

    def gizle(self):
        if self._after_id:
            try:
                self.entry.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.pop is not None:
            try:
                self.pop.withdraw()
            except Exception:
                pass


class EReceteCozucuGUI:
    def __init__(self, master):
        self.win = master
        self.win.title("🔍 E-Reçete No Çözücü")
        try:
            self.win.geometry("880x720")
        except Exception:
            pass

        self.r = _renkler()
        self.win.configure(bg=self.r["bg"])

        self.tablo = get_tablo()
        self.motor = CozucuMotor(self.tablo)
        self._ogrenme = get_ogrenme()

        # Durum
        self.calisiyor = False
        self.durdur_bayrak = False
        self.worker = None

        # tk değişkenleri
        self.mode_var = tk.StringVar(value="erecete")   # "erecete" | "takip"
        self.tc_var = tk.StringVar()
        self.tc_bilgi_var = tk.StringVar(value="")       # TC durum/tamamlama bilgisi
        self.toplu_var = tk.StringVar()                  # toplu (hızlı) giriş
        self.cozum_modu_var = tk.StringVar(value="belirsiz")  # "belirsiz"|"eksik"
        self.prefix_var = tk.IntVar(value=3)             # eksik modu: baştan kesin
        self.eksik_bilgi_var = tk.StringVar(value="")
        self.uzunluk_var = tk.IntVar(value=VARSAYILAN_UZUNLUK)
        self.kesin_vars = [tk.StringVar() for _ in range(KUTU_SAYISI)]
        self.benzet_vars = [tk.StringVar() for _ in range(KUTU_SAYISI)]
        self.olasi_vars = [tk.StringVar() for _ in range(KUTU_SAYISI)]
        self.toplam_var = tk.StringVar(value="Toplam: 0 kombinasyon")
        self.durum_var = tk.StringVar(value="Hazır.")
        self.ilerleme_var = tk.StringVar(value="")

        self._arayuz_kur()
        self._toplami_guncelle()

    # ── Arayüz ────────────────────────────────────────────────────────
    def _arayuz_kur(self):
        r = self.r

        # Başlık
        baslik = tk.Frame(self.win, bg=r["header_bg"])
        baslik.pack(fill="x")
        tk.Label(baslik, text="🔍 E-Reçete No Çözücü",
                 bg=r["header_bg"], fg=r["fg"],
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=14, pady=10)
        tk.Button(baslik, text="⚙ Karışma Tablosu", command=self._ayar_ac,
                  bg=r["card_bg"], fg=r["fg"], relief="flat",
                  activebackground=r["border"], cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="right", padx=12)
        tk.Button(baslik, text="⚡ Mini pencere", command=self._mini_ac,
                  bg=r["card_bg"], fg=r["fg"], relief="flat",
                  activebackground=r["border"], cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="right", padx=2)

        # Üst kontroller: mode switch + TC + uzunluk
        ust = tk.Frame(self.win, bg=r["bg"])
        ust.pack(fill="x", padx=14, pady=(12, 4))

        tk.Label(ust, text="Sorgu Tipi:", bg=r["bg"], fg=r["fg_secondary"],
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        tk.Radiobutton(ust, text="E-Reçete No", variable=self.mode_var,
                       value="erecete", bg=r["bg"], fg=r["fg"],
                       selectcolor=r["card_bg"], activebackground=r["bg"],
                       font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w", padx=4)
        tk.Radiobutton(ust, text="Takip No", variable=self.mode_var,
                       value="takip", bg=r["bg"], fg=r["fg"],
                       selectcolor=r["card_bg"], activebackground=r["bg"],
                       font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=4)

        tk.Label(ust, text="T.C. Kimlik No (ops.):", bg=r["bg"], fg=r["fg_secondary"],
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=3, sticky="e", padx=(24, 4))
        self.tc_entry = tk.Entry(ust, textvariable=self.tc_var, width=16,
                                 font=("Consolas", 12))
        self.tc_entry.grid(row=0, column=4, sticky="w")
        self.tc_entry.bind("<KeyRelease>", lambda e: self._tc_guncelle())
        self._ac = HastaAutocomplete(
            self.win, self.tc_entry, tc_yardimci.hasta_ara,
            self._tc_hasta_secildi, on_enter_bos=self._tc_hasta_ara)

        tk.Label(ust, text="Karakter sayısı:", bg=r["bg"], fg=r["fg_secondary"],
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=5, sticky="e", padx=(24, 4))
        uz = tk.Spinbox(ust, from_=4, to=KUTU_SAYISI, width=4,
                        textvariable=self.uzunluk_var, font=("Segoe UI", 10),
                        command=self._uzunluk_degisti)
        uz.grid(row=0, column=6, sticky="w")
        self.uzunluk_var.trace_add("write", lambda *_: self._uzunluk_degisti())

        # TC durum/tamamlama bilgisi (son 2 hane gizliyse otomatik hesaplanır)
        self.tc_bilgi_lbl = tk.Label(ust, textvariable=self.tc_bilgi_var, bg=r["bg"],
                                     fg=r["fg_secondary"], font=("Consolas", 9),
                                     anchor="w")
        self.tc_bilgi_lbl.grid(row=1, column=3, columnspan=4, sticky="w", padx=(24, 0))
        tk.Label(ust, text="(boş bırakılabilir → Medula'daki TC kullanılır · son 2 hane "
                           "gizliyse ilk 9'u yaz: 452683307 → otomatik tamamlanır)",
                 bg=r["bg"], fg=r["fg_secondary"],
                 font=("Segoe UI", 8)).grid(row=1, column=0, columnspan=3, sticky="w")

        # Çözüm modu seçici
        mod = tk.Frame(self.win, bg=r["bg"])
        mod.pack(fill="x", padx=14, pady=(6, 0))
        tk.Label(mod, text="Çözüm modu:", bg=r["bg"], fg=r["fg_secondary"],
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Radiobutton(mod, text="Karakter belirsiz", variable=self.cozum_modu_var,
                       value="belirsiz", bg=r["bg"], fg=r["fg"], selectcolor=r["card_bg"],
                       activebackground=r["bg"], font=("Segoe UI", 10),
                       command=self._mode_degisti).pack(side="left", padx=4)
        tk.Radiobutton(mod, text="Eksik karakter (bir karakter atlanmış)",
                       variable=self.cozum_modu_var, value="eksik", bg=r["bg"], fg=r["fg"],
                       selectcolor=r["card_bg"], activebackground=r["bg"],
                       font=("Segoe UI", 10), command=self._mode_degisti).pack(side="left", padx=4)

        # Eksik modu kontrolleri (baştan kaç karakter kesin)
        self.eksik_kontrol = tk.Frame(mod, bg=r["bg"])
        self.eksik_kontrol.pack(side="left", padx=(18, 0))
        tk.Label(self.eksik_kontrol, text="Baştan kesin karakter:", bg=r["bg"],
                 fg=r["fg_secondary"], font=("Segoe UI", 10, "bold")).pack(side="left")
        self.prefix_spin = tk.Spinbox(self.eksik_kontrol, from_=0, to=KUTU_SAYISI,
                                      width=4, textvariable=self.prefix_var,
                                      font=("Segoe UI", 10), command=self._toplami_guncelle)
        self.prefix_spin.pack(side="left", padx=4)
        self.prefix_var.trace_add("write", lambda *_: self._toplami_guncelle())

        # Toplu (hızlı) giriş satırı
        toplu = tk.Frame(self.win, bg=r["card_bg"])
        toplu.pack(fill="x", padx=14, pady=(4, 0))
        self.toplu_label = tk.Label(toplu, text="⚡ Toplu giriş:", bg=r["card_bg"],
                                    fg=r["fg"], font=("Segoe UI", 10, "bold"))
        self.toplu_label.pack(side="left", padx=(10, 6), pady=8)
        self.toplu_entry = tk.Entry(toplu, textvariable=self.toplu_var, width=16,
                                    justify="center", font=("Consolas", 15, "bold"))
        self.toplu_entry.pack(side="left", pady=8)
        self.toplu_entry.bind("<KeyRelease>", self._toplu_dagit)
        self.toplu_ipucu = tk.Label(
            toplu, text="numarayı yaz → karakterler aşağıda P1…Pn 'kesin' "
                        "kutularına otomatik dağılır (sonra şüpheli olanı düzenle)",
            bg=r["card_bg"], fg=r["fg_secondary"], font=("Segoe UI", 8))
        self.toplu_ipucu.pack(side="left", padx=10)

        # Kutucuklar — her pozisyonda 3 alan: kesin / benzettiğim / denenecekler
        kutu_cerceve = tk.LabelFrame(
            self.win, text=" Karakterler ",
            bg=r["bg"], fg=r["fg_secondary"], font=("Segoe UI", 10, "bold"),
            bd=1, relief="groove")
        kutu_cerceve.pack(fill="x", padx=14, pady=8)

        self.kesin_entryleri = []
        self.benzet_entryleri = []
        self.olasi_entryleri = []
        self.pos_labelleri = []
        self.onizleme_vars = [tk.StringVar(value="") for _ in range(KUTU_SAYISI)]
        self.onizleme_labelleri = []

        # Tek grid — tüm hücreler satır bazında hizalı
        grid = tk.Frame(kutu_cerceve, bg=r["bg"])
        grid.pack(padx=10, pady=8)

        satir_etiketleri = ["kesin", "benzettiğim", "denenecekler", "→ denenecek"]
        satir_ikonlari = ["✓", "≈", "✎", "→"]
        # Sol etiket sütunu (column 0)
        tk.Label(grid, text="", bg=r["bg"]).grid(row=0, column=0)
        for ri, txt in enumerate(satir_etiketleri, start=1):
            fg = r["success"] if ri == 4 else r["fg_secondary"]
            tk.Label(grid, text=f"{satir_ikonlari[ri-1]} {txt}", bg=r["bg"], fg=fg,
                     font=("Segoe UI", 9), anchor="e").grid(
                row=ri, column=0, sticky="e", padx=(2, 8), pady=3)

        kesin_bg = "#EAF3FF"   # kesin kutusu açık mavi (birincil)
        alt_bg = "#FFFFFF"
        for i in range(KUTU_SAYISI):
            c = i + 1
            # Pozisyon başlığı — chip görünümü
            head = tk.Label(grid, text=f"P{i+1}", bg=r["card_bg"], fg=r["fg"],
                            font=("Segoe UI", 9, "bold"), width=6, pady=2)
            head.grid(row=0, column=c, padx=3, pady=(2, 3))
            self.pos_labelleri.append(head)

            ke = tk.Entry(grid, textvariable=self.kesin_vars[i], width=6,
                          justify="center", font=("Consolas", 14, "bold"),
                          bg=kesin_bg, relief="solid", bd=1)
            ke.grid(row=1, column=c, padx=3, pady=3)
            ke.bind("<KeyRelease>", lambda e: self._toplami_guncelle())
            self.kesin_entryleri.append(ke)

            bz = tk.Entry(grid, textvariable=self.benzet_vars[i], width=6,
                          justify="center", font=("Consolas", 12),
                          bg=alt_bg, relief="solid", bd=1)
            bz.grid(row=2, column=c, padx=3, pady=3)
            bz.bind("<KeyRelease>", lambda e: self._toplami_guncelle())
            self.benzet_entryleri.append(bz)

            ol = tk.Entry(grid, textvariable=self.olasi_vars[i], width=6,
                          justify="center", font=("Consolas", 12),
                          bg=alt_bg, relief="solid", bd=1)
            ol.grid(row=3, column=c, padx=3, pady=3)
            ol.bind("<KeyRelease>", lambda e: self._toplami_guncelle())
            self.olasi_entryleri.append(ol)

            pv = tk.Label(grid, textvariable=self.onizleme_vars[i], bg=r["bg"],
                          fg=r["success"], font=("Consolas", 8),
                          width=9, wraplength=72, justify="center")
            pv.grid(row=4, column=c, padx=3, pady=(2, 4), sticky="n")
            self.onizleme_labelleri.append(pv)

        # Eksik karakter modu bilgi satırı (sadece eksik modunda dolu)
        self.eksik_bilgi_lbl = tk.Label(
            kutu_cerceve, textvariable=self.eksik_bilgi_var, bg=r["bg"],
            fg=r["warning"], font=("Consolas", 9, "bold"),
            wraplength=820, justify="left")
        self.eksik_bilgi_lbl.pack(padx=10, pady=(0, 2), anchor="w")

        # İpucu
        self.ipucu_lbl = tk.Label(kutu_cerceve,
                 text="✓ KESİN → sadece o denenir · ≈ BENZETTİĞİM → karışma tablosundan genişletilir "
                      "(örn. I→I,1,L,T,J) · ✎ DENENECEKLER → elle yazdığın adaylar (virgül/boşluk fark etmez) · "
                      "benzet/denenecekler doluysa kesin'i ezer · üçü de boşsa TÜM karakterler denenir · "
                      "yeşil satır o pozisyonda gerçekten ne deneneceğini gösterir",
                 bg=r["bg"], fg=r["fg_secondary"], font=("Segoe UI", 8),
                 wraplength=820, justify="left")
        self.ipucu_lbl.pack(padx=10, pady=(0, 6), anchor="w")

        # Aksiyon çubuğu
        aksiyon = tk.Frame(self.win, bg=r["bg"])
        aksiyon.pack(fill="x", padx=14, pady=6)

        tk.Label(aksiyon, textvariable=self.toplam_var, bg=r["bg"], fg=r["fg"],
                 font=("Segoe UI", 11, "bold")).pack(side="left")

        self.baslat_btn = tk.Button(aksiyon, text="▶ Başlat", command=self._baslat,
                                    bg=r["success"], fg="white", relief="flat",
                                    font=("Segoe UI", 11, "bold"), cursor="hand2",
                                    padx=18, pady=4)
        self.baslat_btn.pack(side="right", padx=(6, 0))
        self.durdur_btn = tk.Button(aksiyon, text="■ Durdur", command=self._durdur,
                                    bg=r["error"], fg="white", relief="flat",
                                    font=("Segoe UI", 11, "bold"), cursor="hand2",
                                    padx=18, pady=4, state="disabled")
        self.durdur_btn.pack(side="right", padx=6)

        # İlerleme
        ilerleme_cerceve = tk.Frame(self.win, bg=r["bg"])
        ilerleme_cerceve.pack(fill="x", padx=14, pady=(4, 0))
        self.progress = ttk.Progressbar(ilerleme_cerceve, mode="determinate")
        self.progress.pack(fill="x")
        tk.Label(ilerleme_cerceve, textvariable=self.ilerleme_var, bg=r["bg"],
                 fg=r["fg_secondary"], font=("Consolas", 9)).pack(anchor="w")

        # Durum (büyük renkli)
        self.durum_lbl = tk.Label(self.win, textvariable=self.durum_var,
                                  bg=r["bg"], fg=r["fg"], font=("Segoe UI", 12, "bold"),
                                  wraplength=840, justify="left")
        self.durum_lbl.pack(fill="x", padx=14, pady=(6, 2))

        # Log
        log_cerceve = tk.LabelFrame(self.win, text=" Deneme Günlüğü ", bg=r["bg"],
                                    fg=r["fg_secondary"], font=("Segoe UI", 9, "bold"))
        log_cerceve.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self.log = tk.Text(log_cerceve, height=10, bg="#0D1B2A", fg="#D0E0F0",
                           font=("Consolas", 9), relief="flat", state="disabled")
        self.log.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb = tk.Scrollbar(log_cerceve, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.config(yscrollcommand=sb.set)
        self.log.tag_config("ok", foreground="#7CFC7C")
        self.log.tag_config("fail", foreground="#9AB0C8")
        self.log.tag_config("warn", foreground="#FFC864")
        self.log.tag_config("err", foreground="#FF6B6B")

        self._tc_guncelle()
        self._mode_degisti()

    # ── Yardımcılar ───────────────────────────────────────────────────
    def _aktif_uzunluk(self):
        try:
            n = int(self.uzunluk_var.get())
        except Exception:
            n = VARSAYILAN_UZUNLUK
        return max(1, min(KUTU_SAYISI, n))

    def _tc_guncelle(self):
        """TC kutusunu yorumla. 3 durum:
        - boş → Medula'daki TC kullanılır
        - harf içeriyor → isim; Enter'a basınca Botanik EOS'ta aranır
        - rakam → 9 hane girilince otomatik 11'e tamamlanır; durum gösterilir
        """
        giris = self.tc_var.get().strip()
        if not giris:
            self._ac.gizle()
            self.tc_bilgi_var.set("ⓘ boş → Medula TC · isim yaz → hasta listesi açılır")
            self.tc_bilgi_lbl.config(fg=self.r["fg_secondary"])
            return
        if any(c.isalpha() for c in giris):
            self._ac.tetikle(giris)      # canlı açılır öneri listesi
            self.tc_bilgi_var.set("🔎 hasta ara (en sık gelenler üstte)")
            self.tc_bilgi_lbl.config(fg=self.r["fg_secondary"])
            return
        self._ac.gizle()
        # Sadece rakam: 9 hane → otomatik 11'e tamamla
        rakam = "".join(c for c in giris if c.isdigit())
        if len(rakam) == 9:
            tam = tc_yardimci.tc_tamamla(rakam)
            if tam:
                self.tc_var.set(tam)
                self.tc_bilgi_var.set(f"✓ tamamlandı → {tam}")
                self.tc_bilgi_lbl.config(fg=self.r["success"])
                return
        try:
            durum, n, _ilk = tc_yardimci.durum_ozeti(giris)
        except Exception:
            self.tc_bilgi_var.set("")
            return
        renk = {0: self.r["error"], 1: self.r["success"]}.get(n, self.r["warning"])
        onek = {0: "✗", 1: "✓"}.get(n, "●")
        self.tc_bilgi_var.set(f"{onek} {durum}")
        self.tc_bilgi_lbl.config(fg=renk)

    def _tc_hasta_ara(self):
        """TC kutusuna isim yazılmışsa Botanik EOS'ta hasta ara (arka planda)."""
        giris = self.tc_var.get().strip()
        if not giris or not any(c.isalpha() for c in giris):
            return
        self.tc_bilgi_var.set("🔎 Botanik'te aranıyor…")
        self.tc_bilgi_lbl.config(fg=self.r["fg_secondary"])

        def isle():
            try:
                sonuc = tc_yardimci.hasta_ara(giris)
            except Exception:
                sonuc = []
            self.win.after(0, lambda: self._tc_sonuc_goster(sonuc))
        threading.Thread(target=isle, daemon=True).start()

    def _tc_sonuc_goster(self, sonuc):
        if not sonuc:
            self.tc_bilgi_var.set("✗ hasta bulunamadı")
            self.tc_bilgi_lbl.config(fg=self.r["error"])
        elif len(sonuc) == 1:
            self._tc_hasta_secildi(sonuc[0]["tc"], sonuc[0]["ad"])
        else:
            _hasta_sec_popup(self.win, sonuc, self._tc_hasta_secildi)

    def _tc_hasta_secildi(self, tc, ad):
        self.tc_var.set(tc)
        self.tc_bilgi_var.set(f"✓ {ad} → {tc}")
        self.tc_bilgi_lbl.config(fg=self.r["success"])

    def _uzunluk_degisti(self):
        """Seçilen uzunluğa göre kutuları aktifleştir/pasifleştir.
        Eksik modunda kutular tamamen pasiftir (toplu giriş kullanılır)."""
        n = self._aktif_uzunluk()
        r = self.r
        eksik = self.cozum_modu_var.get() == "eksik"
        for i in range(KUTU_SAYISI):
            aktif = (i < n) and not eksik
            durum = "normal" if aktif else "disabled"
            try:
                self.kesin_entryleri[i].config(state=durum)
                self.benzet_entryleri[i].config(state=durum)
                self.olasi_entryleri[i].config(state=durum)
                self.pos_labelleri[i].config(
                    fg=r["fg"] if aktif else r["border"],
                    bg=r["card_bg"] if aktif else r["bg"])
                self.onizleme_labelleri[i].config(
                    fg=r["success"] if aktif else r["border"])
            except Exception:
                pass
        self._toplami_guncelle()

    def _toplu_dagit(self, _evt=None):
        """Toplu giriş kutusundaki numarayı P1..Pn 'kesin' kutularına dağıt.

        Her anlamlı karakter (harf/rakam) sırayla bir pozisyona yazılır;
        karakter sayısı otomatik ayarlanır. Benzet/denenecekler temizlenir
        (yeni numara sıfırdan girildiği varsayımı).

        Eksik modunda dağıtım YAPILMAZ — toplu kutu 'yazılan eksik numara'dır."""
        if self.cozum_modu_var.get() == "eksik":
            self._toplami_guncelle()
            return
        ham = self.toplu_var.get()
        chars = [c.upper() for c in ham if c.isalnum()]
        n = len(chars)
        if n:
            self.uzunluk_var.set(max(1, min(KUTU_SAYISI, n)))
        for i in range(KUTU_SAYISI):
            self.kesin_vars[i].set(chars[i] if i < n else "")
            self.benzet_vars[i].set("")
            self.olasi_vars[i].set("")
        self._toplami_guncelle()

    def _mode_degisti(self):
        """Çözüm modu değişince arayüzü uyarlar (belirsiz ↔ eksik)."""
        r = self.r
        eksik = self.cozum_modu_var.get() == "eksik"
        # Eksik kontrolleri (prefix spinbox) sadece eksik modunda
        try:
            self.prefix_spin.config(state="normal" if eksik else "disabled")
        except Exception:
            pass
        # Toplu giriş etiketi ve ipucu moda göre
        if eksik:
            self.toplu_label.config(text="✍ Yazılan numara:")
            self.toplu_ipucu.config(
                text="doktorun yazdığı EKSİK numarayı gir (örn. 2OX5GH) → "
                     "eksik karakter tüm ara pozisyonlara sırayla eklenip denenir")
            self.eksik_bilgi_lbl.config(fg=r["warning"])
            self.ipucu_lbl.pack_forget()
        else:
            self.toplu_label.config(text="⚡ Toplu giriş:")
            self.toplu_ipucu.config(
                text="numarayı yaz → karakterler aşağıda P1…Pn 'kesin' "
                     "kutularına otomatik dağılır (sonra şüpheli olanı düzenle)")
            self.eksik_bilgi_var.set("")
            try:
                self.ipucu_lbl.pack(padx=10, pady=(0, 6), anchor="w")
            except Exception:
                pass
        self._uzunluk_degisti()  # kutu aktif/pasif + _toplami_guncelle

    def _pozisyonlar(self):
        n = self._aktif_uzunluk()
        poz = []
        for i in range(KUTU_SAYISI):
            poz.append(Pozisyon(
                kesin=self.kesin_vars[i].get(),
                benzet=self.benzet_vars[i].get(),
                olasi=self.olasi_vars[i].get(),
                aktif=(i < n),
            ))
        return poz

    def _toplami_guncelle(self):
        # Eksik karakter modu
        if self.cozum_modu_var.get() == "eksik":
            self._eksik_guncelle()
            return
        poz = self._pozisyonlar()
        try:
            toplam = self.motor.toplam_kombinasyon(poz)
        except Exception:
            toplam = 0
        self.toplam_var.set(f"Toplam: {toplam:,} kombinasyon".replace(",", "."))
        # Her pozisyonun canlı önizlemesini güncelle
        ks = self.motor.karakter_seti
        for i, p in enumerate(poz):
            try:
                if not p.aktif:
                    self.onizleme_vars[i].set("")
                    continue
                durum, adaylar = p.durum_ozeti(ks, self.motor.tablo)
                if durum == "TÜMÜ":
                    self.onizleme_vars[i].set("(tümü)")
                else:
                    goster = ",".join(adaylar[:8])
                    if len(adaylar) > 8:
                        goster += f"…(+{len(adaylar) - 8})"
                    self.onizleme_vars[i].set(goster)
            except Exception:
                self.onizleme_vars[i].set("")

    def _eksik_guncelle(self):
        """Eksik modu: toplam + bilgi + insertion şablonlarını göster."""
        yazilan = self.toplu_var.get()
        try:
            prefix = int(self.prefix_var.get())
        except Exception:
            prefix = 0
        hedef = self._aktif_uzunluk()
        # Pozisyon önizlemelerini temizle (bu modda kullanılmıyor)
        for i in range(KUTU_SAYISI):
            self.onizleme_vars[i].set("")
        try:
            L, M, G, toplam = self.motor.eksik_bilgi(yazilan, prefix, hedef)
        except Exception:
            L, M, G, toplam = 0, 0, 0, 0
        self.toplam_var.set(f"Toplam: {toplam:,} kombinasyon".replace(",", "."))
        if not yazilan.strip():
            self.eksik_bilgi_var.set("Yukarıya doktorun yazdığı eksik numarayı girin.")
            return
        if M <= 0:
            self.eksik_bilgi_var.set(
                f"⚠ Yazılan {L} karakter, hedef uzunluk {hedef}. Eksik karakter yok "
                f"(yazılan hedeften kısa olmalı). Karakter sayısını artırın veya "
                f"'Karakter belirsiz' moduna geçin.")
            return
        s = self.motor._norm_yazilan(yazilan)
        gaps = self.motor._eksik_gaps(len(s), prefix)
        if M == 1:
            sablon = "  →  ".join(s[:g] + "▯" + s[g:] for g in gaps)
        else:
            sablon = f"{M} eksik karakter {G} boşluğa dağıtılır"
        self.eksik_bilgi_var.set(
            f"Yazılan {L} karakter · {M} eksik · {G} olası pozisyon × "
            f"{len(self.motor.karakter_seti)} karakter = {toplam:,} deneme\n{sablon}"
            .replace(",", "."))

    def _log_yaz(self, metin, tag=None):
        try:
            self.log.config(state="normal")
            self.log.insert("end", metin + "\n", tag or ())
            self.log.see("end")
            self.log.config(state="disabled")
        except Exception:
            pass

    def _ui(self, fn):
        """Worker thread'inden GUI güncellemesi planla."""
        try:
            self.win.after(0, fn)
        except Exception:
            pass

    # ── Çalıştırma ────────────────────────────────────────────────────
    def _baslat(self):
        if self.calisiyor:
            return

        # TC adaylarını çöz (son 2 hane gizliyse hesaplanır; iç joker varsa
        # geçerli tüm adaylar denenir). Boşsa Medula'daki mevcut TC kullanılır.
        tc_giris = self.tc_var.get().strip()
        if tc_giris:
            tc_list = tc_yardimci.tc_adaylari(tc_giris)
            if not tc_list:
                messagebox.showwarning(
                    "TC", "Girilen TC'den geçerli bir kimlik numarası "
                    "tamamlanamadı. İlk 9 haneyi doğru girdiğinizden emin olun "
                    "(son 2 hane gizliyse ilk 9'u yazmanız yeterli).",
                    parent=self.win)
                return
        else:
            tc_list = [None]

        # Ekran hazır mı?
        uygun, mesaj = medula.sorgu_ekraninda_mi()
        if not uygun:
            messagebox.showerror("Medula", mesaj, parent=self.win)
            return

        # Moda göre kombinasyonları üret
        cmod = self.cozum_modu_var.get()
        if cmod == "eksik":
            yazilan = self.toplu_var.get()
            try:
                prefix = int(self.prefix_var.get())
            except Exception:
                prefix = 0
            hedef = self._aktif_uzunluk()
            L, M, G, toplam = self.motor.eksik_bilgi(yazilan, prefix, hedef)
            if M <= 0:
                messagebox.showwarning(
                    "Eksik karakter", "Yazılan numara hedef uzunluktan kısa olmalı "
                    "(en az 1 eksik karakter). Karakter sayısını kontrol edin.",
                    parent=self.win)
                return
            kombolar = list(self.motor.eksik_kombinasyonlar(yazilan, prefix, hedef))
        else:
            poz = self._pozisyonlar()
            toplam = self.motor.toplam_kombinasyon(poz)
            kombolar = list(self.motor.kombinasyonlar(poz))

        if toplam <= 0 or not kombolar:
            messagebox.showwarning("Boş", "Denenecek kombinasyon yok. "
                                   "En az bir karakter girin.", parent=self.win)
            return

        # Toplam deneme = TC adayı sayısı × numara kombinasyonu sayısı
        genel_toplam = len(tc_list) * len(kombolar)
        tc_notu = ""
        if len(tc_list) > 1:
            tc_notu = f" × {len(tc_list)} TC adayı"
        if genel_toplam > UYARI_ESIGI:
            devam = messagebox.askyesno(
                "Çok fazla kombinasyon",
                f"{genel_toplam:,} deneme yapılacak".replace(",", ".") +
                f" ({len(kombolar)} numara{tc_notu}).\n\n"
                "Bu çok sayıda Medula sorgusu demektir ve uzun sürebilir. "
                "Daha az karakteri belirsiz bırakmanız önerilir.\n\nDevam edilsin mi?",
                parent=self.win)
            if not devam:
                return

        mode = self.mode_var.get()

        self.calisiyor = True
        self.durdur_bayrak = False
        self.baslat_btn.config(state="disabled")
        self.durdur_btn.config(state="normal")
        self.progress.config(maximum=genel_toplam, value=0)
        self.durum_var.set("Deneniyor...")
        self.durum_lbl.config(fg=self.r["fg"])
        self._log_yaz(f"=== Başladı: {genel_toplam} deneme "
                      f"({len(kombolar)} numara{tc_notu}) · tip={mode} ===", "warn")

        self.worker = threading.Thread(
            target=self._dongu, args=(kombolar, mode, tc_list), daemon=True)
        self.worker.start()

    def _durdur(self):
        self.durdur_bayrak = True
        self.durum_var.set("Durduruluyor...")

    def _dongu(self, kombolar, mode, tc_list):
        """Worker thread: (TC adayı × numara kombinasyonu) sırayla dener."""
        import medula_html_dom as mhd
        import time
        hwnd = mhd._medula_hwnd()
        belirsiz_ardisik = 0
        toplam = len(tc_list) * len(kombolar)
        coklu_tc = len(tc_list) > 1
        i = 0

        for tc in tc_list:
            tc_etiket = (tc or "—")
            if coklu_tc:
                self._ui(lambda tc=tc_etiket: self._log_yaz(
                    f"— TC adayı: {tc} —", "warn"))
            for kombo in kombolar:
                if self.durdur_bayrak:
                    self._ui(lambda: self._bitti(False, "Kullanıcı durdurdu."))
                    return
                i += 1
                etiket = f"{kombo}  (TC {tc_etiket})" if coklu_tc else kombo
                self._ui(lambda i=i, etiket=etiket: self._ilerleme_guncelle(
                    i, toplam, etiket))

                durum, mesaj = medula.tek_dene(kombo, mode=mode, tc=tc, hwnd=hwnd)

                if durum == medula.BULUNAMADI:
                    belirsiz_ardisik = 0
                    self._ui(lambda i=i, etiket=etiket: self._log_yaz(
                        f"  [{i}/{toplam}] {etiket}  ✗ bulunamadı", "fail"))
                elif durum == medula.BULUNDU:
                    try:
                        self._ogrenme.ogren(mode, kombo)   # prefix+tür öğren
                    except Exception:
                        pass
                    self._ui(lambda i=i, etiket=etiket: self._log_yaz(
                        f"  [{i}/{toplam}] {etiket}  ✓ BULUNDU!", "ok"))
                    ok, m2 = medula.sonuc_satirini_ac(hwnd=hwnd)
                    bulgu = f"e-reçete/takip: {kombo}"
                    if tc:
                        bulgu += f" · TC: {tc}"
                    self._ui(lambda bulgu=bulgu, m2=m2: self._bitti(
                        True, f"✓ Reçete bulundu ({bulgu})\n{m2}"))
                    return
                elif durum == medula.HATA:
                    self._ui(lambda i=i, etiket=etiket, mesaj=mesaj: self._log_yaz(
                        f"  [{i}/{toplam}] {etiket}  ⚠ HATA: {mesaj}", "err"))
                    self._ui(lambda mesaj=mesaj: self._bitti(
                        False, f"Hata nedeniyle durdu: {mesaj}"))
                    return
                else:  # BELİRSİZ
                    belirsiz_ardisik += 1
                    self._ui(lambda i=i, etiket=etiket: self._log_yaz(
                        f"  [{i}/{toplam}] {etiket}  ? belirsiz", "warn"))
                    if belirsiz_ardisik >= BELIRSIZ_LIMIT:
                        self._ui(lambda: self._bitti(
                            False, f"{BELIRSIZ_LIMIT} ardışık belirsiz sonuç — durdu. "
                            "Medula ekranını kontrol edin (doğru sayfa/TC?)."))
                        return

                time.sleep(0.4)  # Medula'yı yormamak için nezaket beklemesi

        self._ui(lambda: self._bitti(
            False, "Tüm denemeler bitti — reçete bulunamadı."))

    def _ilerleme_guncelle(self, i, toplam, etiket):
        self.progress.config(value=i)
        self.ilerleme_var.set(f"{i} / {toplam}   →   deneniyor: {etiket}")

    def _bitti(self, basarili, mesaj):
        self.calisiyor = False
        self.durdur_bayrak = False
        self.baslat_btn.config(state="normal")
        self.durdur_btn.config(state="disabled")
        self.durum_var.set(mesaj)
        self.durum_lbl.config(fg=self.r["success"] if basarili else self.r["warning"])
        self._log_yaz(f"=== Bitti: {mesaj} ===",
                      "ok" if basarili else "warn")

    # ── Ayar penceresi (karışma tablosu) ──────────────────────────────
    def _ayar_ac(self):
        AyarPenceresi(self.win, self.tablo, on_kaydet=self._toplami_guncelle)

    def _mini_ac(self):
        MiniCozucuGUI(self.win)


class AyarPenceresi:
    """Karışma tablosunu düzenleme penceresi."""

    def __init__(self, parent, tablo: KarismaTablosu, on_kaydet=None):
        self.tablo = tablo
        self.on_kaydet = on_kaydet
        self.r = _renkler()
        self.win = tk.Toplevel(parent)
        self.win.title("⚙ Karışma Tablosu")
        self.win.geometry("460x560")
        self.win.configure(bg=self.r["bg"])
        self.win.transient(parent)
        self._kur()
        self._listeyi_doldur()

    def _kur(self):
        r = self.r
        tk.Label(self.win, text="Birbiriyle karışabilen karakter grupları",
                 bg=r["bg"], fg=r["fg"], font=("Segoe UI", 11, "bold")).pack(pady=(10, 2))
        tk.Label(self.win,
                 text="Her satır bir karışma grubudur. Gruptaki karakterlerin\n"
                      "hepsi birbiriyle karışabilir kabul edilir. Örn: QO0DC",
                 bg=r["bg"], fg=r["fg_secondary"], font=("Segoe UI", 8)).pack()

        liste_cerceve = tk.Frame(self.win, bg=r["bg"])
        liste_cerceve.pack(fill="both", expand=True, padx=12, pady=8)
        self.liste = tk.Listbox(liste_cerceve, font=("Consolas", 12),
                                bg="#0D1B2A", fg="#D0E0F0", selectmode="single",
                                activestyle="none")
        self.liste.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(liste_cerceve, command=self.liste.yview)
        sb.pack(side="right", fill="y")
        self.liste.config(yscrollcommand=sb.set)
        self.liste.bind("<<ListboxSelect>>", self._secildi)

        giris = tk.Frame(self.win, bg=r["bg"])
        giris.pack(fill="x", padx=12)
        self.giris_var = tk.StringVar()
        ent = tk.Entry(giris, textvariable=self.giris_var, font=("Consolas", 13))
        ent.pack(side="left", fill="x", expand=True)
        tk.Button(giris, text="Ekle", command=self._ekle, bg=r["success"],
                  fg="white", relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 0))

        btnler = tk.Frame(self.win, bg=r["bg"])
        btnler.pack(fill="x", padx=12, pady=8)
        tk.Button(btnler, text="Seçiliyi Güncelle", command=self._guncelle,
                  bg=r["card_bg"], fg=r["fg"], relief="flat", cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left")
        tk.Button(btnler, text="Seçiliyi Sil", command=self._sil,
                  bg=r["error"], fg="white", relief="flat", cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left", padx=6)
        tk.Button(btnler, text="Varsayılana Dön", command=self._varsayilan,
                  bg=r["warning"], fg="white", relief="flat", cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="right")

        alt = tk.Frame(self.win, bg=r["bg"])
        alt.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(alt, text="💾 Kaydet ve Kapat", command=self._kaydet_kapat,
                  bg=r["success"], fg="white", relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold"), pady=6).pack(fill="x")

    def _listeyi_doldur(self):
        self.liste.delete(0, "end")
        for s in self.tablo.setler:
            self.liste.insert("end", s)

    def _secildi(self, _evt=None):
        sel = self.liste.curselection()
        if sel:
            self.giris_var.set(self.liste.get(sel[0]))

    def _ekle(self):
        try:
            self.tablo.set_ekle(self.giris_var.get())
            self._listeyi_doldur()
            self.giris_var.set("")
        except ValueError as e:
            messagebox.showwarning("Geçersiz", str(e), parent=self.win)

    def _guncelle(self):
        sel = self.liste.curselection()
        if not sel:
            messagebox.showinfo("Seçim", "Önce listeden bir grup seçin.", parent=self.win)
            return
        try:
            self.tablo.set_guncelle(sel[0], self.giris_var.get())
            self._listeyi_doldur()
        except ValueError as e:
            messagebox.showwarning("Geçersiz", str(e), parent=self.win)

    def _sil(self):
        sel = self.liste.curselection()
        if not sel:
            return
        self.tablo.set_sil(sel[0])
        self._listeyi_doldur()

    def _varsayilan(self):
        if messagebox.askyesno("Varsayılana Dön",
                               "Tüm değişiklikler silinip varsayılan tabloya "
                               "dönülsün mü?", parent=self.win):
            self.tablo.varsayilana_don()
            self._listeyi_doldur()

    def _kaydet_kapat(self):
        try:
            self.tablo.kaydet()
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}", parent=self.win)
            return
        if self.on_kaydet:
            try:
                self.on_kaydet()
            except Exception:
                pass
        self.win.destroy()


class MiniCozucuGUI:
    """Sol üst köşede kalan küçük, her zaman üstte (topmost) hızlı çözücü.

    Kullanıcı TC (ops.) + tek bir numara girer. Sistem numaranın e-reçete mi
    takip mi olduğunu otomatik anlar, önce numarayı olduğu gibi dener, açılmazsa
    EN ÇOK KARIŞAN karakterleri (önce 1, sonra 2 değişim) karışma tablosuna
    göre hızlıca dener. 'Medulayı canlı tut' işaretliyse oturum arka planda
    20sn'de bir uyanık tutulur.
    """

    def __init__(self, master=None):
        self._sahip_root = master is None
        self.win = tk.Tk() if master is None else tk.Toplevel(master)
        self.win.title("⚡ Hızlı Çözücü")
        try:
            self.win.attributes("-topmost", True)
            self.win.geometry("340x300+8+8")   # sol üst köşe
            self.win.resizable(False, False)
        except Exception:
            pass
        self.r = _renkler()
        self.win.configure(bg=self.r["bg"])

        self.tablo = get_tablo()
        self.motor = CozucuMotor(self.tablo)
        self._ogrenme = get_ogrenme()
        self._medula_prefix = {}     # {'erecete':'2P3','takip':'59X'} — Medula'dan

        self.calisiyor = False
        self.durdur_bayrak = False
        self.worker = None
        self._ka_thread = None
        self._ka_stop = threading.Event()

        self.tc_var = tk.StringVar()
        self.tc_bilgi_var = tk.StringVar(value="")
        self.num_var = tk.StringVar()
        self.topmost_var = tk.BooleanVar(value=True)   # 📌 her zaman üstte
        self.tip_override = None          # None=oto | "erecete" | "takip"
        self.derin_var = tk.BooleanVar(value=False)   # 2 karakter değişim
        self.canli_var = tk.BooleanVar(value=False)
        self.tip_var = tk.StringVar(value="Tip: —")
        self.durum_var = tk.StringVar(value="Hazır.")

        self._kur()
        self.win.protocol("WM_DELETE_WINDOW", self._kapat)

    def _kur(self):
        r = self.r
        head = tk.Frame(self.win, bg=r["header_bg"])
        head.pack(fill="x")
        tk.Label(head, text="⚡ Hızlı Çözücü", bg=r["header_bg"], fg=r["fg"],
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=6, pady=3)
        self.pin_chk = tk.Checkbutton(
            head, text="📌 Üstte", variable=self.topmost_var,
            command=self._topmost_toggle, bg=r["header_bg"], fg=r["fg"],
            selectcolor=r["header_bg"], activebackground=r["header_bg"],
            activeforeground=r["fg"], font=("Segoe UI", 8, "bold"),
            bd=0, cursor="hand2")
        self.pin_chk.pack(side="right", padx=6)

        gov = tk.Frame(self.win, bg=r["bg"])
        gov.pack(fill="both", expand=True, padx=8, pady=6)

        tk.Label(gov, text="TC / isim:", bg=r["bg"], fg=r["fg_secondary"],
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="e", pady=2)
        self.tc_entry = tk.Entry(gov, textvariable=self.tc_var, width=18,
                                 font=("Consolas", 11))
        self.tc_entry.grid(row=0, column=1, sticky="w", padx=4)
        self.tc_entry.bind("<KeyRelease>", lambda e: self._tc_guncelle())
        self._ac = HastaAutocomplete(
            self.win, self.tc_entry, tc_yardimci.hasta_ara,
            self._tc_hasta_secildi, on_enter_bos=self._tc_hasta_ara)

        self.tc_bilgi_lbl = tk.Label(gov, textvariable=self.tc_bilgi_var, bg=r["bg"],
                                     fg=r["fg_secondary"], font=("Consolas", 8),
                                     wraplength=320, justify="left")
        self.tc_bilgi_lbl.grid(row=1, column=0, columnspan=2, sticky="w")

        tk.Label(gov, text="Numara:", bg=r["bg"], fg=r["fg_secondary"],
                 font=("Segoe UI", 9)).grid(row=2, column=0, sticky="e", pady=2)
        self.num_entry = tk.Entry(gov, textvariable=self.num_var, width=18,
                                  font=("Consolas", 14, "bold"))
        self.num_entry.grid(row=2, column=1, sticky="w", padx=4)
        self.num_entry.bind("<KeyRelease>", lambda e: self._tip_guncelle())
        self.num_entry.bind("<Return>", lambda e: self._coz())

        tipf = tk.Frame(gov, bg=r["bg"])
        tipf.grid(row=3, column=0, columnspan=2, sticky="w")
        self.tip_lbl = tk.Label(tipf, textvariable=self.tip_var, bg=r["bg"],
                                fg=r["fg_secondary"], font=("Segoe UI", 9, "bold"),
                                cursor="hand2")
        self.tip_lbl.pack(side="left", padx=(2, 4))
        self.tip_lbl.bind("<Button-1>", lambda e: self._tip_dongu())
        tk.Button(tipf, text="⟳ prefiks", command=self._medula_prefix_oku,
                  bg=r["card_bg"], fg=r["fg"], relief="flat", cursor="hand2",
                  font=("Segoe UI", 7)).pack(side="left")
        tk.Label(tipf, text="(tür seç → ilk 3 hane dolar)", bg=r["bg"],
                 fg=r["fg_secondary"], font=("Segoe UI", 7)).pack(side="left", padx=4)

        tk.Checkbutton(gov, text="derin ara (2 karakter)", variable=self.derin_var,
                       bg=r["bg"], fg=r["fg"], selectcolor=r["card_bg"],
                       activebackground=r["bg"], font=("Segoe UI", 8)).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.canli_chk = tk.Checkbutton(
            gov, text="Medulayı canlı tut", variable=self.canli_var,
            bg=r["bg"], fg=r["fg"], selectcolor=r["card_bg"],
            activebackground=r["bg"], font=("Segoe UI", 9),
            command=self._canli_toggle)
        self.canli_chk.grid(row=5, column=0, columnspan=2, sticky="w")

        btnf = tk.Frame(gov, bg=r["bg"])
        btnf.grid(row=6, column=0, columnspan=2, pady=(4, 2), sticky="we")
        self.coz_btn = tk.Button(btnf, text="🔓 Çöz", command=self._coz,
                                 bg=r["success"], fg="white", relief="flat",
                                 font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.coz_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))
        self.dur_btn = tk.Button(btnf, text="■ Dur", command=self._durdur,
                                 bg=r["error"], fg="white", relief="flat",
                                 font=("Segoe UI", 10, "bold"), cursor="hand2",
                                 state="disabled")
        self.dur_btn.pack(side="left", expand=True, fill="x", padx=(3, 0))

        self.durum_lbl = tk.Label(gov, textvariable=self.durum_var, bg=r["bg"],
                                  fg=r["fg"], font=("Segoe UI", 8), wraplength=320,
                                  justify="left")
        self.durum_lbl.grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.progress = ttk.Progressbar(gov, mode="determinate", length=320)
        self.progress.grid(row=8, column=0, columnspan=2, sticky="we", pady=(2, 0))
        self._tc_guncelle()
        # Açılışta Medula prefix tablosunu sessizce oku (varsa)
        try:
            self.win.after(700, lambda: self._medula_prefix_oku(sessiz=True))
        except Exception:
            pass

    def _topmost_toggle(self):
        """📌 işareti: pencerenin her zaman üstte kalma özelliğini aç/kapat."""
        try:
            self.win.attributes("-topmost", bool(self.topmost_var.get()))
        except Exception:
            pass

    # ── TC / isim işleme ──────────────────────────────────────────────
    def _tc_guncelle(self):
        giris = self.tc_var.get().strip()
        if not giris:
            self._ac.gizle()
            self.tc_bilgi_var.set("boş → Medula TC · isim yaz → liste")
            self.tc_bilgi_lbl.config(fg=self.r["fg_secondary"])
            return
        if any(c.isalpha() for c in giris):
            self._ac.tetikle(giris)
            self.tc_bilgi_var.set("🔎 hasta ara (en sık üstte)")
            self.tc_bilgi_lbl.config(fg=self.r["fg_secondary"])
            return
        self._ac.gizle()
        rakam = "".join(c for c in giris if c.isdigit())
        if len(rakam) == 9:
            tam = tc_yardimci.tc_tamamla(rakam)
            if tam:
                self.tc_var.set(tam)
                self.tc_bilgi_var.set(f"✓ tamamlandı → {tam}")
                self.tc_bilgi_lbl.config(fg=self.r["success"])
                return
        try:
            durum, n, _ = tc_yardimci.durum_ozeti(giris)
        except Exception:
            self.tc_bilgi_var.set("")
            return
        renk = {0: self.r["error"], 1: self.r["success"]}.get(n, self.r["warning"])
        onek = {0: "✗", 1: "✓"}.get(n, "●")
        self.tc_bilgi_var.set(f"{onek} {durum}")
        self.tc_bilgi_lbl.config(fg=renk)

    def _tc_hasta_ara(self):
        giris = self.tc_var.get().strip()
        if not giris or not any(c.isalpha() for c in giris):
            return
        self.tc_bilgi_var.set("🔎 Botanik'te aranıyor…")
        self.tc_bilgi_lbl.config(fg=self.r["fg_secondary"])

        def isle():
            try:
                sonuc = tc_yardimci.hasta_ara(giris)
            except Exception:
                sonuc = []
            self._ui(lambda: self._tc_sonuc_goster(sonuc))
        threading.Thread(target=isle, daemon=True).start()

    def _tc_sonuc_goster(self, sonuc):
        if not sonuc:
            self.tc_bilgi_var.set("✗ hasta bulunamadı")
            self.tc_bilgi_lbl.config(fg=self.r["error"])
        elif len(sonuc) == 1:
            self._tc_hasta_secildi(sonuc[0]["tc"], sonuc[0]["ad"])
        else:
            _hasta_sec_popup(self.win, sonuc, self._tc_hasta_secildi)

    def _tc_hasta_secildi(self, tc, ad):
        self.tc_var.set(tc)
        self.tc_bilgi_var.set(f"✓ {ad} → {tc}")
        self.tc_bilgi_lbl.config(fg=self.r["success"])

    # ── Tip tespiti ───────────────────────────────────────────────────
    def _tip_guncelle(self):
        if self.tip_override:
            ad = "E-Reçete" if self.tip_override == "erecete" else "Takip"
            self.tip_var.set(f"Tip: yalnız {ad}")
            return
        num = self.num_var.get()
        tip, ogr = self._ogrenme.tip_belirle(num)
        ad = "E-Reçete" if tip == "erecete" else "Takip"
        if ogr:
            pfx = self._ogrenme.eslesen_prefix(num) or ""
            self.tip_var.set(f"Oto: {ad} ✓öğr.{pfx}")
        else:
            self.tip_var.set(f"Oto: {ad} → sonra diğeri")

    def _tip_dongu(self):
        # oto (öğrenilmişse direkt, değilse ikisini dener) → erecete → takip
        self.tip_override = {None: "erecete", "erecete": "takip",
                             "takip": None}[self.tip_override]
        if self.tip_override in ("erecete", "takip"):
            self._prefix_uygula(self.tip_override)
        self._tip_guncelle()

    # ── Prefix (ilk 3 hane) otomatik doldurma ─────────────────────────
    def _prefix_al(self, tip):
        """Bir tür için en iyi bilinen 3-karakter prefix (Medula cache → öğrenilen)."""
        p = (self._medula_prefix or {}).get(tip)
        if not p:
            p = self._ogrenme.guncel_prefix(tip)
        return p

    def _prefix_uygula(self, tip):
        """Seçilen türün ilk-3 prefix'ini numara kutusuna yaz; kalan (4) hane
        korunur. Kutu boşsa sadece prefix yazılır, imleç sona gider."""
        prefix = self._prefix_al(tip)
        if not prefix:
            # Bilinmiyorsa Medula'dan oku (okununca tekrar uygulanır)
            self._medula_prefix_oku()
            return
        mevcut = "".join(c for c in self.num_var.get() if c.isalnum()).upper()
        kalan = mevcut[len(prefix):] if len(mevcut) > len(prefix) else ""
        self.num_var.set(prefix + kalan)
        try:
            self.num_entry.focus_set()
            self.num_entry.icursor("end")
        except Exception:
            pass

    def _medula_prefix_oku(self, sessiz=False):
        """Medula E-Reçete Sorgu ekranındaki prefix tablolarını (arka planda)
        okuyup öğren; seçili tür varsa kutuya uygula. sessiz=True → hata
        durumunda uyarı gösterme (açılışta otomatik okuma için)."""
        if not sessiz:
            self._durum("Medula'dan prefiksler okunuyor…")

        def isle():
            try:
                p = medula.prefix_tablosu_oku()
            except Exception:
                p = {"erecete": [], "takip": []}
            self._ui(lambda: self._medula_prefix_geldi(p, sessiz))
        threading.Thread(target=isle, daemon=True).start()

    def _medula_prefix_geldi(self, p, sessiz=False):
        er = p.get("erecete") or []
        tk_ = p.get("takip") or []
        if er:
            self._medula_prefix["erecete"] = er[0]
        if tk_:
            self._medula_prefix["takip"] = tk_[0]
        try:
            self._ogrenme.meduladan_kaydet(er, tk_)
        except Exception:
            pass
        if not er and not tk_:
            if not sessiz:
                self._durum("Medula prefix tablosu okunamadı (E-Reçete Sorgu "
                            "ekranı açık mı?).", r_err=True)
            return
        self._durum(f"Prefiks: E-Reçete={self._medula_prefix.get('erecete','?')} · "
                    f"Takip={self._medula_prefix.get('takip','?')}")
        if self.tip_override in ("erecete", "takip"):
            self._prefix_uygula(self.tip_override)

    def _mode_sirasi(self, num):
        """(modes, confident) döndürür.
        - override → [tek], True
        - öğrenilmiş prefix → [öğrenilen, diğer], True (direkt öğrenileni dene)
        - bilinmiyor → [heuristik, diğer], False (iki alanın orijinali önce)
        """
        if self.tip_override:
            return [self.tip_override], True
        tip, ogr = self._ogrenme.tip_belirle(num)
        diger = "takip" if tip == "erecete" else "erecete"
        return [tip, diger], ogr

    # ── Çözüm ─────────────────────────────────────────────────────────
    def _coz(self):
        if self.calisiyor:
            return
        num = "".join(c for c in self.num_var.get() if c.isalnum()).upper()
        if not num:
            self._durum("Numara girin.", r_err=True)
            return
        tc_giris = self.tc_var.get().strip()
        if tc_giris:
            tc_list = tc_yardimci.tc_adaylari(tc_giris)
            if not tc_list:
                self._durum("Geçersiz TC (ilk 9 haneyi kontrol edin).", r_err=True)
                return
        else:
            tc_list = [None]

        uygun, mesaj = medula.sorgu_ekraninda_mi()
        if not uygun:
            self._durum(mesaj, r_err=True)
            return

        modes, confident = self._mode_sirasi(num)
        max_deg = 2 if self.derin_var.get() else 1
        tum = list(self.motor.otomatik_kombinasyonlar(num, max_degisim=max_deg))
        orijinal = tum[0] if tum else num
        degisimler = tum[1:]

        if confident or len(modes) == 1:
            # Tür biliniyor (öğrenildi/sabit) → DOĞRUDAN o alanı tam dene,
            # (güvenlik için) sonra diğerini tam dene.
            sekans = []
            for mo in modes:
                sekans.append((mo, orijinal))
                for c in degisimler:
                    sekans.append((mo, c))
        else:
            # Tür bilinmiyor → önce her iki alanın ORİJİNAL numarası (yanlış
            # tespit ilk 2 sorguda telafi), sonra karışma değişimleri.
            sekans = [(mo, orijinal) for mo in modes]
            for mo in modes:
                for c in degisimler:
                    sekans.append((mo, c))
        genel = len(tc_list) * len(sekans)

        self.calisiyor = True
        self.durdur_bayrak = False
        self.coz_btn.config(state="disabled")
        self.dur_btn.config(state="normal")
        self.progress.config(maximum=genel, value=0)
        ad = "her ikisi" if len(modes) > 1 else (
            "E-Reçete" if modes[0] == "erecete" else "Takip")
        self._durum(f"Deneniyor… ({genel} deneme · {ad})")

        self.worker = threading.Thread(
            target=self._dongu, args=(sekans, tc_list), daemon=True)
        self.worker.start()

    def _durdur(self):
        self.durdur_bayrak = True

    def _dongu(self, sekans, tc_list):
        import medula_html_dom as mhd
        import time
        hwnd = mhd._medula_hwnd()
        toplam = len(tc_list) * len(sekans)
        belirsiz = 0
        i = 0
        for tc in tc_list:
            for mode, kombo in sekans:
                if self.durdur_bayrak:
                    self._ui(lambda: self._bitti(False, "Durduruldu."))
                    return
                i += 1
                etiket = f"{kombo} [{'E-Reç' if mode == 'erecete' else 'Takip'}]"
                self._ui(lambda i=i, etiket=etiket: self._ilerleme(i, toplam, etiket))
                durum, _m = medula.tek_dene(kombo, mode=mode, tc=tc, hwnd=hwnd)
                if durum == medula.BULUNDU:
                    medula.sonuc_satirini_ac(hwnd=hwnd)
                    try:
                        self._ogrenme.ogren(mode, kombo)   # prefix+tür öğren
                    except Exception:
                        pass
                    tur = "E-Reçete" if mode == "erecete" else "Takip"
                    b = f"{kombo} ({tur})" + (f" · TC {tc}" if tc else "")
                    self._ui(lambda b=b: self._bitti(True, f"✓ Açıldı: {b}"))
                    return
                elif durum == medula.HATA:
                    self._ui(lambda _m=_m: self._bitti(False, f"Hata: {_m}"))
                    return
                elif durum == medula.BELIRSIZ:
                    belirsiz += 1
                    if belirsiz >= BELIRSIZ_LIMIT:
                        self._ui(lambda: self._bitti(
                            False, "Belirsiz sonuç — Medula ekranını kontrol edin."))
                        return
                else:
                    belirsiz = 0
                time.sleep(0.35)
        self._ui(lambda: self._bitti(False, "Bulunamadı (tüm denemeler bitti)."))

    def _ilerleme(self, i, toplam, etiket):
        self.progress.config(value=i)
        self._durum(f"{i}/{toplam} → {etiket}")

    def _bitti(self, basarili, mesaj):
        self.calisiyor = False
        self.durdur_bayrak = False
        self.coz_btn.config(state="normal")
        self.dur_btn.config(state="disabled")
        self.durum_lbl.config(fg=self.r["success"] if basarili else self.r["warning"])
        self.durum_var.set(mesaj)

    def _durum(self, metin, r_err=False):
        self.durum_lbl.config(fg=self.r["error"] if r_err else self.r["fg"])
        self.durum_var.set(metin)

    def _ui(self, fn):
        try:
            self.win.after(0, fn)
        except Exception:
            pass

    # ── Medula canlı tut (keepalive) ──────────────────────────────────
    def _canli_toggle(self):
        if self.canli_var.get():
            self._ka_stop.clear()
            self._ka_thread = threading.Thread(target=self._ka_loop, daemon=True)
            self._ka_thread.start()
        else:
            self._ka_stop.set()

    def _ka_loop(self):
        try:
            import medula_keepalive as ka
        except Exception:
            return
        while not self._ka_stop.is_set():
            try:
                w = ka.medula_penceresi_bul()
                if w is not None and ka.oturum_aktif_mi(w):
                    ka.keepalive_tiklama(w)
            except Exception:
                pass
            self._ka_stop.wait(20)

    def _kapat(self):
        self.durdur_bayrak = True
        self._ka_stop.set()
        try:
            self.win.destroy()
        except Exception:
            pass
        if self._sahip_root:
            try:
                self.win.quit()
            except Exception:
                pass


def mini_cozucu_ac(parent=None):
    """Mini topmost hızlı çözücüyü aç."""
    if parent is None:
        gui = MiniCozucuGUI(None)
        gui.win.mainloop()
        return None
    return MiniCozucuGUI(parent)


def erecete_cozucu_ac(parent=None):
    """Modülü aç. parent bir Toplevel/root ise onu kullanır; yoksa yeni açar."""
    if parent is None:
        root = tk.Tk()
        gui = EReceteCozucuGUI(root)
        root.mainloop()
        return None
    win = parent if isinstance(parent, (tk.Tk, tk.Toplevel)) else tk.Toplevel(parent)
    return EReceteCozucuGUI(win)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "mini":
        mini_cozucu_ac(None)
    else:
        erecete_cozucu_ac(None)
