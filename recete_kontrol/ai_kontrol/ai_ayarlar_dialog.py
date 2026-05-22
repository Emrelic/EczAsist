"""AI Kontrol Ayarlar Diyaloğu (Tkinter).

Kullanıcının kendi Anthropic API anahtarını girmesi, model seçimi yapması,
günlük limit belirlemesi için modal pencere.

İçerik:
    • API key (gizli alan + 'Göster' toggle)
    • 'Bağlantıyı Test Et' butonu
    • Varsayılan model: Sonnet 4.6 / Opus 4.7 / Haiku 4.5
    • Günlük çağrı limiti (entry)
    • Günlük maliyet limiti USD (entry)
    • Bugünkü kullanım özeti (otomatik gösterilir)
    • KVKK onay durumu + onay verme butonu
    • Kaydet / İptal
"""
from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional

from . import ai_istemci, ai_log_db, ayarlar, claude_code_subprocess, debug_dialoglari

logger = logging.getLogger(__name__)


class AIAyarlarDialog(tk.Toplevel):
    """AI Kontrol Ayarlar modal penceresi."""

    def __init__(self, parent: tk.Misc, on_save: Optional[callable] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_save = on_save
        self._kapatildi = False

        self.title("🤖 AI Kontrol Ayarları")
        self.geometry("680x760")
        self.minsize(600, 680)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._mevcut = ayarlar.ayarlari_yukle()
        self._kur_ui()
        self._mevcudu_doldur()
        self._kullanim_ozetini_guncelle()

        self.protocol("WM_DELETE_WINDOW", self._iptal)
        self.bind("<Escape>", lambda _e: self._iptal())

    # ──────────────────────────────────────────────
    # UI iskelet
    # ──────────────────────────────────────────────
    def _kur_ui(self) -> None:
        # Başlık
        baslik = tk.Frame(self, bg="#3949AB", height=46)
        baslik.pack(fill="x", side="top")
        baslik.pack_propagate(False)
        tk.Label(
            baslik, text="🤖 AI Kontrol Ayarları",
            bg="#3949AB", fg="white",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left", padx=12, pady=10)

        # Ana içerik (scrollable)
        ana = tk.Frame(self, bg="white")
        ana.pack(fill="both", expand=True, padx=12, pady=8)

        # ── 0. BACKEND SEÇİMİ ──
        f0 = tk.LabelFrame(
            ana, text="Backend (AI sağlayıcı yöntemi)",
            font=("Segoe UI", 9, "bold"),
            bg="white", fg="#0277BD", padx=8, pady=6,
        )
        f0.pack(fill="x", pady=(0, 6))

        self.var_backend = tk.StringVar(value=ayarlar.BACKEND_API)
        rb_api = ttk.Radiobutton(
            f0,
            text="Anthropic API — kendi API anahtarınız (pay-per-use)",
            variable=self.var_backend, value=ayarlar.BACKEND_API,
            command=self._backend_degisti,
        )
        rb_api.pack(anchor="w", pady=1)
        rb_sub = ttk.Radiobutton(
            f0,
            text="Claude Code subprocess — Max planınız (ek fatura yok)",
            variable=self.var_backend, value=ayarlar.BACKEND_SUBPROCESS,
            command=self._backend_degisti,
        )
        rb_sub.pack(anchor="w", pady=1)

        self.lbl_backend_durum = tk.Label(
            f0, text="", bg="white", fg="#37474F",
            font=("Segoe UI", 8, "italic"),
            justify="left", anchor="w", wraplength=600,
        )
        self.lbl_backend_durum.pack(anchor="w", pady=(4, 0))

        # ── 1. API key ──
        f1 = tk.LabelFrame(
            ana, text="Anthropic API Anahtarı (sadece API backend için)",
            font=("Segoe UI", 9, "bold"),
            bg="white", fg="#1A237E", padx=8, pady=6,
        )
        self._frame_api_key = f1
        f1.pack(fill="x", pady=(0, 6))

        tk.Label(
            f1,
            text=("Kendi Anthropic anahtarınızı girin (sk-ant-... ile başlar).\n"
                  "Anahtarınız ai_config.json içinde yerel makinenizde saklanır,\n"
                  "asla başka yere gönderilmez."),
            bg="white", fg="#37474F", justify="left",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(0, 4))

        key_row = tk.Frame(f1, bg="white")
        key_row.pack(fill="x")
        self.var_api_key = tk.StringVar()
        self.var_goster = tk.BooleanVar(value=False)
        self.ent_api_key = ttk.Entry(
            key_row, textvariable=self.var_api_key, show="•", width=50,
        )
        self.ent_api_key.pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(
            key_row, text="Göster", variable=self.var_goster,
            command=self._goster_toggle,
        ).pack(side="left", padx=6)

        self.btn_test = ttk.Button(
            f1, text="🔌 Bağlantıyı Test Et",
            command=self._baglanti_test,
        )
        self.btn_test.pack(anchor="w", pady=(4, 0))
        self.lbl_test = tk.Label(
            f1, text="", bg="white", fg="#37474F",
            font=("Segoe UI", 8, "italic"), wraplength=560, justify="left",
        )
        self.lbl_test.pack(anchor="w", pady=(2, 0))

        # ── 2. Model seçimi ──
        f2 = tk.LabelFrame(
            ana, text="Varsayılan Model",
            font=("Segoe UI", 9, "bold"),
            bg="white", fg="#1A237E", padx=8, pady=6,
        )
        f2.pack(fill="x", pady=6)

        self.var_model = tk.StringVar(value=ayarlar.MODEL_SONNET)
        for m_id in ayarlar.GECERLI_MODELLER:
            ttk.Radiobutton(
                f2,
                text=ayarlar.MODEL_ETIKETLERI[m_id],
                variable=self.var_model,
                value=m_id,
            ).pack(anchor="w", pady=1)

        # ── 3. Limitler ──
        f3 = tk.LabelFrame(
            ana, text="Günlük Limitler",
            font=("Segoe UI", 9, "bold"),
            bg="white", fg="#1A237E", padx=8, pady=6,
        )
        f3.pack(fill="x", pady=6)

        lr = tk.Frame(f3, bg="white")
        lr.pack(fill="x")
        tk.Label(lr, text="Çağrı sayısı:", bg="white",
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.var_lim_cagri = tk.StringVar(value="100")
        ttk.Entry(lr, textvariable=self.var_lim_cagri, width=10).grid(
            row=0, column=1, sticky="w", padx=4)
        tk.Label(lr, text="(0 = sınırsız)", bg="white",
                 fg="#666", font=("Segoe UI", 8)).grid(row=0, column=2, sticky="w")

        tk.Label(lr, text="Maliyet (USD):", bg="white",
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self.var_lim_maliyet = tk.StringVar(value="5.0")
        ttk.Entry(lr, textvariable=self.var_lim_maliyet, width=10).grid(
            row=1, column=1, sticky="w", padx=4)
        tk.Label(lr, text="(0 = sınırsız)", bg="white",
                 fg="#666", font=("Segoe UI", 8)).grid(row=1, column=2, sticky="w")

        tk.Label(lr, text="Yanıt max token:", bg="white",
                 font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", padx=2, pady=2)
        self.var_max_tok = tk.StringVar(value="8000")
        ttk.Entry(lr, textvariable=self.var_max_tok, width=10).grid(
            row=2, column=1, sticky="w", padx=4)

        tk.Label(lr, text="Subprocess timeout (sn):", bg="white",
                 font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", padx=2, pady=2)
        self.var_timeout = tk.StringVar(value="600")
        ttk.Entry(lr, textvariable=self.var_timeout, width=10).grid(
            row=3, column=1, sticky="w", padx=4)
        tk.Label(lr, text="(kombi/karmaşık ilaçlarda 600+ önerilir)",
                 bg="white", fg="#666",
                 font=("Segoe UI", 8)).grid(row=3, column=2, sticky="w")

        # Klinik yorum opsiyonu — uzun analiz iste/isteme
        self.var_klinik = tk.BooleanVar(value=True)
        cb_klinik = ttk.Checkbutton(
            lr,
            text="🎯 Uzun klinik yorum iste (sohbet tonu, 300-600 kelime analiz)",
            variable=self.var_klinik,
        )
        cb_klinik.grid(row=4, column=0, columnspan=3, sticky="w", padx=2, pady=(6, 2))
        tk.Label(
            lr,
            text=("   ⚠ Açık: detaylı klinik analiz (yavaş, 60-180 sn/reçete)\n"
                  "   ⚡ Kapalı: hızlı toplu kontrol modu (sadece etiket+özet, 10-30 sn)"),
            bg="white", fg="#666",
            font=("Segoe UI", 8), justify="left", anchor="w",
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=2, pady=(0, 4))

        # ── 4. Bugünkü kullanım ──
        f4 = tk.LabelFrame(
            ana, text="Bugünkü Kullanım",
            font=("Segoe UI", 9, "bold"),
            bg="white", fg="#1A237E", padx=8, pady=6,
        )
        f4.pack(fill="x", pady=6)
        self.lbl_kullanim = tk.Label(
            f4, text="(yükleniyor...)", bg="white", fg="#37474F",
            font=("Consolas", 9), justify="left", anchor="w",
        )
        self.lbl_kullanim.pack(anchor="w")

        # ── 5. KVKK ──
        f5 = tk.LabelFrame(
            ana, text="KVKK Onayı",
            font=("Segoe UI", 9, "bold"),
            bg="white", fg="#B71C1C", padx=8, pady=6,
        )
        f5.pack(fill="x", pady=6)

        self.lbl_kvkk = tk.Label(
            f5, text="", bg="white", fg="#37474F",
            font=("Segoe UI", 9), justify="left", wraplength=560,
        )
        self.lbl_kvkk.pack(anchor="w")

        self.btn_kvkk = ttk.Button(
            f5, text="KVKK Onayı Ver / İptal Et",
            command=self._kvkk_toggle,
        )
        self.btn_kvkk.pack(anchor="w", pady=4)

        # ── Alt butonlar ──
        alt = tk.Frame(self, bg="#ECEFF1", height=46)
        alt.pack(fill="x", side="bottom")
        alt.pack_propagate(False)

        # Sol — debug/şeffaflık butonları
        ttk.Button(
            alt, text="📄 Sistem Promptu Gör",
            command=lambda: debug_dialoglari.sistem_promptu_goster(self),
        ).pack(side="left", padx=8, pady=8)
        ttk.Button(
            alt, text="📊 Çağrı Logu",
            command=lambda: debug_dialoglari.cagri_logu_goster(self),
        ).pack(side="left", padx=2, pady=8)

        # Sağ — kaydet/iptal
        ttk.Button(alt, text="İptal", command=self._iptal).pack(
            side="right", padx=8, pady=8)
        ttk.Button(alt, text="💾 Kaydet", command=self._kaydet).pack(
            side="right", padx=2, pady=8)

    # ──────────────────────────────────────────────
    # Veri doldur / oku
    # ──────────────────────────────────────────────
    def _mevcudu_doldur(self) -> None:
        c = self._mevcut
        self.var_backend.set(c.get("backend") or ayarlar.BACKEND_API)
        self.var_api_key.set(c.get("api_key") or "")
        self.var_model.set(c.get("varsayilan_model") or ayarlar.MODEL_SONNET)
        self.var_lim_cagri.set(str(c.get("gunluk_cagri_limiti") or 100))
        self.var_lim_maliyet.set(str(c.get("gunluk_maliyet_limiti_usd") or 5.0))
        self.var_max_tok.set(str(c.get("max_tokens_yaniti") or 8000))
        self.var_timeout.set(str(c.get("subprocess_timeout_sn") or 600))
        self.var_klinik.set(bool(c.get("klinik_yorum_iste", True)))
        self._kvkk_metnini_guncelle()
        self._backend_degisti()

    def _backend_degisti(self) -> None:
        """Backend radio değişince UI'i güncelle: API key alanı + durum etiketi."""
        secim = self.var_backend.get()
        if secim == ayarlar.BACKEND_SUBPROCESS:
            # claude komutunun durumunu göster
            ok, msg = claude_code_subprocess.saglik_kontrolu()
            if ok:
                self.lbl_backend_durum.config(
                    text="✓ " + msg + "\nMax planınız üzerinden kullanılır; "
                    "API anahtarı gerekmez, ek fatura kesilmez.",
                    fg="#2E7D32",
                )
            else:
                self.lbl_backend_durum.config(
                    text="✗ " + msg, fg="#C62828",
                )
            # API key alanını disabled yap
            try:
                self.ent_api_key.config(state="disabled")
                self.btn_test.config(state="normal")  # subprocess test edilebilir
            except Exception:
                pass
        else:
            self.lbl_backend_durum.config(
                text=("Anthropic API: kendi anahtarınızla çağrılır. "
                      "Pay-per-use, console.anthropic.com'dan bakiye yüklenmeli."),
                fg="#01579B",
            )
            try:
                self.ent_api_key.config(state="normal")
                self.btn_test.config(state="normal")
            except Exception:
                pass

    def _kvkk_metnini_guncelle(self) -> None:
        c = ayarlar.ayarlari_yukle()
        if c.get("kvkk_onay"):
            self.lbl_kvkk.config(
                text=(f"✓ KVKK onayı VERİLDİ ({c.get('kvkk_onay_tarih', '')}).\n"
                      "AI butonu hasta verisini anonim formatta Anthropic'e gönderebilir."),
                fg="#2E7D32",
            )
        else:
            self.lbl_kvkk.config(
                text=("⚠ KVKK onayı YOK.\n"
                      "AI butonu kullanılmadan önce, hasta verisinin (TC hash, "
                      "yaş, cinsiyet, teşhis, ilaçlar, rapor) anonim formatta "
                      "Anthropic'e (ABD) gönderileceği onayını vermelisiniz."),
                fg="#B71C1C",
            )

    def _kullanim_ozetini_guncelle(self) -> None:
        try:
            ozet = ai_log_db.gunluk_ozet()
        except Exception:
            ozet = {"cagri_sayisi": 0, "maliyet_usd": 0.0,
                    "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
        metin = (
            f"Çağrı sayısı     : {ozet.get('cagri_sayisi', 0)}\n"
            f"Input tokens     : {ozet.get('input_tokens', 0):,}\n"
            f"Output tokens    : {ozet.get('output_tokens', 0):,}\n"
            f"Cache hit tokens : {ozet.get('cached_tokens', 0):,}\n"
            f"Toplam maliyet   : ${ozet.get('maliyet_usd', 0.0):.4f}"
        )
        self.lbl_kullanim.config(text=metin)

    # ──────────────────────────────────────────────
    # Aksiyonlar
    # ──────────────────────────────────────────────
    def _goster_toggle(self) -> None:
        self.ent_api_key.config(show="" if self.var_goster.get() else "•")

    def _baglanti_test(self) -> None:
        # Ekrandaki ayarları diske yaz, sonra test (ai_istemci dosyadan okur).
        secim_backend = self.var_backend.get()
        eski = ayarlar.ayarlari_yukle()
        gec = dict(eski)
        gec["backend"] = secim_backend
        gec["api_key"] = self.var_api_key.get().strip()
        gec["varsayilan_model"] = self.var_model.get()

        if secim_backend == ayarlar.BACKEND_API and not gec["api_key"]:
            messagebox.showwarning(
                "API Key", "API backend için önce anahtarı girin.",
                parent=self)
            return

        ayarlar.ayarlari_kaydet(gec)

        self.btn_test.config(state="disabled")
        self.lbl_test.config(text="⏳ Test ediliyor...", fg="#37474F")

        def _isle():
            ok, msg = ai_istemci.baglanti_test_et(model=self.var_model.get())
            self.after(0, lambda: self._test_sonucu_goster(ok, msg))

        threading.Thread(target=_isle, daemon=True).start()

    def _test_sonucu_goster(self, ok: bool, msg: str) -> None:
        self.btn_test.config(state="normal")
        if ok:
            self.lbl_test.config(text="✓ " + msg, fg="#2E7D32")
        else:
            self.lbl_test.config(text="✗ " + msg, fg="#C62828")

    def _kvkk_toggle(self) -> None:
        c = ayarlar.ayarlari_yukle()
        if c.get("kvkk_onay"):
            # Onayı kaldır
            if messagebox.askyesno("KVKK", "KVKK onayını geri çekmek istiyor musunuz?\nAI butonu pasif olur."):
                c["kvkk_onay"] = False
                c["kvkk_onay_tarih"] = ""
                ayarlar.ayarlari_kaydet(c)
                self._kvkk_metnini_guncelle()
        else:
            # Onay diyaloğu
            metin = (
                "Bu butona basarak aşağıdaki bilgilerin Anthropic Inc. (ABD) "
                "sunucularına gönderilebileceğini KABUL EDİYORUM:\n\n"
                "✓ Reçete numarası, tarih, teşhis kodları\n"
                "✓ İlaç adı, ATC kodu, doz, kutu\n"
                "✓ Hasta yaşı, cinsiyeti (TC numarası HASH'lenir, ad/soyad GÖNDERİLMEZ)\n"
                "✓ Rapor metni, etken madde, doktor branşı\n"
                "✓ Hasta'nın geçmiş raporları + ilaç geçmişi (anonim)\n\n"
                "Bu veriler model eğitimi için kullanılmaz.\n"
                "İstediğiniz zaman bu onayı geri çekebilirsiniz.\n\n"
                "Onayı vermek için EVET seçin."
            )
            if messagebox.askyesno("KVKK Onayı", metin, parent=self):
                ayarlar.kvkk_onay_ver()
                self._kvkk_metnini_guncelle()

    def _kaydet(self) -> None:
        try:
            lim_cagri = int(self.var_lim_cagri.get() or "0")
        except ValueError:
            messagebox.showerror("Hata", "Çağrı limiti geçerli sayı olmalı.")
            return
        try:
            lim_maliyet = float(self.var_lim_maliyet.get() or "0")
        except ValueError:
            messagebox.showerror("Hata", "Maliyet limiti geçerli sayı olmalı.")
            return
        try:
            max_tok = int(self.var_max_tok.get() or "4000")
        except ValueError:
            messagebox.showerror("Hata", "Max token geçerli sayı olmalı.")
            return

        try:
            timeout_sn = int(self.var_timeout.get() or "600")
        except ValueError:
            messagebox.showerror("Hata", "Timeout geçerli sayı olmalı.")
            return

        yeni = {
            "backend": self.var_backend.get(),
            "api_key": self.var_api_key.get().strip(),
            "varsayilan_model": self.var_model.get(),
            "gunluk_cagri_limiti": max(0, lim_cagri),
            "gunluk_maliyet_limiti_usd": max(0.0, lim_maliyet),
            "max_tokens_yaniti": max(500, min(16000, max_tok)),
            "subprocess_timeout_sn": max(60, min(1800, timeout_sn)),
            "klinik_yorum_iste": bool(self.var_klinik.get()),
        }
        if ayarlar.ayarlari_kaydet(yeni):
            messagebox.showinfo("Kaydedildi", "AI ayarları kaydedildi.", parent=self)
            if self.on_save:
                try:
                    self.on_save()
                except Exception as e:
                    logger.warning("on_save hook: %s", e)
            self._kapatildi = True
            self.destroy()
        else:
            messagebox.showerror("Hata", "Ayarlar kaydedilemedi (loglara bak).", parent=self)

    def _iptal(self) -> None:
        self._kapatildi = True
        self.destroy()


def ayarlari_ac(parent: tk.Misc, on_save: Optional[callable] = None) -> None:
    """Ana ekrandan AI Ayarlar diyaloğunu aç."""
    AIAyarlarDialog(parent, on_save=on_save)
