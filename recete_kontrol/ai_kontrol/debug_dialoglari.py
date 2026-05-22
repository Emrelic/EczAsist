"""AI Kontrol Debug/Şeffaflık Diyalogları.

İçerik:
    • sistem_promptu_goster(parent)   → SISTEM_PROMPT + few-shot modal
    • cagri_logu_goster(parent)       → ai_log_db son N kayıt + detay
"""
from __future__ import annotations

import json
import logging
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

from . import ai_log_db, prompt_sablonlari

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# 1. Sistem Prompt Görüntüleyici
# ══════════════════════════════════════════════════════════════════════

class SistemPromptDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.title("📄 AI Sistem Promptu (SUT Kontrol Talimatları)")
        self.geometry("960x720")
        self.minsize(700, 560)
        self.transient(parent)
        self.grab_set()

        # Üst
        ust = tk.Frame(self, bg="#283593", height=46)
        ust.pack(fill="x", side="top")
        ust.pack_propagate(False)
        tk.Label(ust, text="📄 AI Sistem Promptu — AI'a her çağrıda gönderilen talimatlar",
                 bg="#283593", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=10)

        # Notebook
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Sistem prompt sekmesi
        f1 = tk.Frame(nb, bg="white")
        nb.add(f1, text="🎯 SISTEM_PROMPT")
        self._scroll_text(f1, prompt_sablonlari.SISTEM_PROMPT)

        # Few-shot örnekleri sekmesi
        f2 = tk.Frame(nb, bg="white")
        nb.add(f2, text="📚 Few-shot Örnekler")
        fewshot_metni = ""
        for i, ornek in enumerate(prompt_sablonlari.FEWSHOT_ORNEKLERI, 1):
            etiket = ("[KULLANICI MESAJI]" if ornek["rol"] == "kullanici"
                      else "[ASİSTAN CEVABI]")
            fewshot_metni += f"═══ Örnek {i} — {etiket} ═══\n\n{ornek['icerik']}\n\n\n"
        self._scroll_text(f2, fewshot_metni)

        # Alt — istatistik + butonlar
        alt = tk.Frame(self, bg="#ECEFF1", height=48)
        alt.pack(fill="x", side="bottom")
        alt.pack_propagate(False)

        sp_char = len(prompt_sablonlari.SISTEM_PROMPT)
        sp_tok = int(sp_char / 3.5)
        tk.Label(
            alt,
            text=(f"Sistem prompt: {sp_char:,} char (~{sp_tok:,} token)  "
                  f"|  Few-shot örneği: {len(prompt_sablonlari.FEWSHOT_ORNEKLERI)} adet  "
                  f"|  Cache: ephemeral 1h (API mode)"),
            bg="#ECEFF1", fg="#37474F",
            font=("Consolas", 9), anchor="w",
        ).pack(side="left", padx=12, pady=6)

        ttk.Button(alt, text="Kapat", command=self.destroy).pack(
            side="right", padx=8, pady=8)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _scroll_text(self, parent: tk.Misc, metin: str) -> None:
        f = tk.Frame(parent, bg="white")
        f.pack(fill="both", expand=True)
        ysb = ttk.Scrollbar(f, orient="vertical")
        ysb.pack(side="right", fill="y")
        txt = tk.Text(f, wrap="word",
                       font=("Consolas", 9),
                       yscrollcommand=ysb.set,
                       bg="#FAFAFA", fg="#212121",
                       bd=1, relief="solid")
        txt.pack(fill="both", expand=True)
        ysb.config(command=txt.yview)
        txt.insert("1.0", metin)
        txt.config(state="disabled")


def sistem_promptu_goster(parent: tk.Misc) -> None:
    SistemPromptDialog(parent)


# ══════════════════════════════════════════════════════════════════════
# 2. Çağrı Logu Görüntüleyici
# ══════════════════════════════════════════════════════════════════════

# Sonuç → renk eşlemesi (tablo arka planı)
_SONUC_BG = {
    "UYGUN": "#C8E6C9",
    "UYGUN_DEGIL": "#FFCDD2",
    "SUPHELI": "#FFF9C4",
    "KONTROL_EDILEMEDI": "#FFF9C4",
    "YETERSIZ_VERI": "#FFE0B2",
    "MANUEL_KONTROL_GEREKIR": "#FFE0B2",
    "HATA": "#ECEFF1",
}


class CagriLoguDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.title("📊 AI Çağrı Logu")
        self.geometry("1200x720")
        self.minsize(800, 560)
        self.transient(parent)
        self.grab_set()

        # Üst — filtre + yenile
        ust = tk.Frame(self, bg="#37474F", height=46)
        ust.pack(fill="x", side="top")
        ust.pack_propagate(False)
        tk.Label(ust, text="📊 AI Çağrı Logu",
                 bg="#37474F", fg="white",
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=12, pady=10)

        kontrol_frame = tk.Frame(ust, bg="#37474F")
        kontrol_frame.pack(side="right", padx=12, pady=8)
        tk.Label(kontrol_frame, text="Son N kayıt:", bg="#37474F", fg="white",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.var_limit = tk.StringVar(value="100")
        ttk.Combobox(kontrol_frame, textvariable=self.var_limit,
                      values=["50", "100", "250", "500"], width=6,
                      state="readonly").pack(side="left", padx=(0, 6))
        ttk.Button(kontrol_frame, text="🔄 Yenile",
                    command=self._yukle).pack(side="left")

        # Üst yarı: tablo
        sol_frame = tk.Frame(self, bg="white")
        sol_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        kolonlar = ("id", "tarih", "model", "recete", "ilac", "sonuc",
                    "guven", "in_tok", "out_tok", "cost", "latency", "hata")
        self.tv = ttk.Treeview(sol_frame, columns=kolonlar, show="headings",
                                selectmode="browse", height=14)
        baslik_genislik = {
            "id": ("ID", 50),
            "tarih": ("Tarih", 140),
            "model": ("Model", 140),
            "recete": ("Reçete No", 100),
            "ilac": ("İlaç", 200),
            "sonuc": ("Sonuç", 120),
            "guven": ("Güven", 60),
            "in_tok": ("In tok", 60),
            "out_tok": ("Out tok", 60),
            "cost": ("Cost $", 80),
            "latency": ("Süre ms", 70),
            "hata": ("Hata", 200),
        }
        for k, (b, g) in baslik_genislik.items():
            self.tv.heading(k, text=b)
            self.tv.column(k, width=g, minwidth=30, stretch=(k in ("ilac", "hata")))

        ysb1 = ttk.Scrollbar(sol_frame, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=ysb1.set)
        ysb1.pack(side="right", fill="y")
        self.tv.pack(side="left", fill="both", expand=True)

        # Renk tag'leri
        for sonuc, bg in _SONUC_BG.items():
            self.tv.tag_configure(sonuc, background=bg)

        self.tv.bind("<<TreeviewSelect>>", self._secim_degisti)
        self.tv.bind("<Double-1>", lambda _e: self._detay_goster())

        # Alt yarı: detay paneli (cevap + hata + meta)
        alt_frame = tk.Frame(self, bg="#ECEFF1")
        alt_frame.pack(fill="both", expand=False, padx=8, pady=(4, 4))

        tk.Label(alt_frame, text="Seçili kaydın detayı (çift tıkla = büyük göster):",
                 bg="#ECEFF1", fg="#37474F",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=4, pady=2)

        det_inner = tk.Frame(alt_frame, bg="white")
        det_inner.pack(fill="both", expand=True)
        ysb2 = ttk.Scrollbar(det_inner, orient="vertical")
        ysb2.pack(side="right", fill="y")
        self.txt_detay = tk.Text(det_inner, height=10, wrap="word",
                                  font=("Consolas", 9),
                                  yscrollcommand=ysb2.set,
                                  bg="#FAFAFA", fg="#212121",
                                  bd=1, relief="solid")
        self.txt_detay.pack(fill="both", expand=True)
        ysb2.config(command=self.txt_detay.yview)

        # Alt — özet + butonlar
        alt_btn = tk.Frame(self, bg="#ECEFF1", height=48)
        alt_btn.pack(fill="x", side="bottom")
        alt_btn.pack_propagate(False)
        self.lbl_ozet = tk.Label(alt_btn, text="",
                                  bg="#ECEFF1", fg="#37474F",
                                  font=("Consolas", 9), anchor="w")
        self.lbl_ozet.pack(side="left", padx=12, pady=6)
        ttk.Button(alt_btn, text="Kapat", command=self.destroy).pack(
            side="right", padx=8, pady=8)
        ttk.Button(alt_btn, text="🔍 Detay penceresi",
                    command=self._detay_goster).pack(side="right", padx=2, pady=8)
        ttk.Button(alt_btn, text="📋 Cevabı kopyala",
                    command=self._cevabi_kopyala).pack(side="right", padx=2, pady=8)

        self._kayitlar: list[Dict[str, Any]] = []
        self._yukle()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

    # ──────────────────────────────────────────────
    # Veri yükleme
    # ──────────────────────────────────────────────
    def _yukle(self) -> None:
        try:
            limit = int(self.var_limit.get())
        except ValueError:
            limit = 100
        self._kayitlar = ai_log_db.son_cagrilar(limit=limit)
        self.tv.delete(*self.tv.get_children())
        toplam_cost = 0.0
        for k in self._kayitlar:
            sonuc = (k.get("sonuc_etiketi") or "").strip()
            cost = float(k.get("maliyet_usd") or 0.0)
            toplam_cost += cost
            values = (
                k.get("id"),
                (k.get("tarih") or "")[:19],
                (k.get("model") or "")[:30],
                (k.get("recete_no") or "")[:18],
                (k.get("ilac_adi") or "")[:50],
                sonuc,
                f"{float(k.get('guven_skoru') or 0):.2f}",
                k.get("input_tokens") or 0,
                k.get("output_tokens") or 0,
                f"${cost:.4f}",
                k.get("latency_ms") or 0,
                (k.get("hata") or "")[:80],
            )
            tag = sonuc if sonuc in _SONUC_BG else ""
            self.tv.insert("", "end", iid=str(k.get("id")),
                            values=values, tags=(tag,) if tag else ())

        self.txt_detay.delete("1.0", "end")
        self.lbl_ozet.config(text=(
            f"Toplam: {len(self._kayitlar)} kayıt  |  "
            f"Cost (metric): ${toplam_cost:.4f}  |  "
            f"(Subprocess backend'de cost metric — Max planda fatura yok)"
        ))

    # ──────────────────────────────────────────────
    # Tablo seçim → detay paneli
    # ──────────────────────────────────────────────
    def _secim_degisti(self, _event=None) -> None:
        sec = self.tv.selection()
        if not sec:
            return
        kayit_id = int(sec[0])
        kayit = next((k for k in self._kayitlar if k.get("id") == kayit_id), None)
        if not kayit:
            return
        self.txt_detay.delete("1.0", "end")
        ozet = (
            f"=== KAYIT #{kayit['id']}  ({kayit.get('tarih', '')}) ===\n"
            f"Model      : {kayit.get('model', '')}\n"
            f"Reçete     : {kayit.get('recete_no', '')}  |  İlaç: {kayit.get('ilac_adi', '')}\n"
            f"SUT madde  : {kayit.get('sut_madde', '')}\n"
            f"Sonuç      : {kayit.get('sonuc_etiketi', '')}  "
            f"(güven {float(kayit.get('guven_skoru') or 0):.2f})\n"
            f"Token      : in={kayit.get('input_tokens')}  "
            f"out={kayit.get('output_tokens')}  "
            f"cache_read={kayit.get('cached_input_tokens')}  "
            f"cache_write={kayit.get('cache_write_tokens')}\n"
            f"Maliyet    : ${float(kayit.get('maliyet_usd') or 0):.4f}  "
            f"|  Süre: {kayit.get('latency_ms')}ms\n"
            f"Prompt hash: {kayit.get('prompt_hash', '')}\n"
        )
        if kayit.get("hata"):
            ozet += f"\n--- HATA ---\n{kayit['hata']}\n"
        cevap = kayit.get("cevap_text") or ""
        if cevap:
            ozet += f"\n--- AI CEVABI (ham) ---\n{cevap}\n"
        self.txt_detay.insert("1.0", ozet)

    def _detay_goster(self) -> None:
        sec = self.tv.selection()
        if not sec:
            messagebox.showinfo("Detay", "Önce bir kayıt seçin.", parent=self)
            return
        kayit_id = int(sec[0])
        kayit = next((k for k in self._kayitlar if k.get("id") == kayit_id), None)
        if not kayit:
            return
        # Yeni modal — büyük cevap görünümü
        win = tk.Toplevel(self)
        win.title(f"Çağrı Detay #{kayit['id']}")
        win.geometry("900x700")
        win.transient(self)
        ysb = ttk.Scrollbar(win, orient="vertical")
        ysb.pack(side="right", fill="y")
        t = tk.Text(win, wrap="word", font=("Consolas", 10),
                    yscrollcommand=ysb.set, bg="#FAFAFA")
        t.pack(fill="both", expand=True)
        ysb.config(command=t.yview)
        t.insert("1.0", self.txt_detay.get("1.0", "end"))

    def _cevabi_kopyala(self) -> None:
        sec = self.tv.selection()
        if not sec:
            return
        kayit_id = int(sec[0])
        kayit = next((k for k in self._kayitlar if k.get("id") == kayit_id), None)
        if not kayit:
            return
        cevap = kayit.get("cevap_text") or ""
        if not cevap:
            messagebox.showinfo("Kopyala", "Bu kayıtta cevap metni yok.", parent=self)
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(cevap)
            self.update()
            messagebox.showinfo("Kopyalandı", f"{len(cevap):,} karakter kopyalandı.",
                                parent=self)
        except Exception as e:
            messagebox.showerror("Hata", f"{e}", parent=self)


def cagri_logu_goster(parent: tk.Misc) -> None:
    CagriLoguDialog(parent)
