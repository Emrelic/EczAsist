"""Screenshot ile AI Sorgu — Toplama Dialogu + Bölge Seçimi + AI Gönderim.

Akış:
  1. ScreenshotSorguDialog açılır (seçili tablo satırından hasta + reçete bilgisi).
  2. Kullanıcı "📷 Screenshot Al" / F9 → BolgeSecimOverlay açılır.
  3. Kullanıcı mausla dikdörtgen çizer, bırakır → PIL ile crop edilip kaydedilir.
  4. Etiket onay pop-up'ı (varsayılan: <ad>_<recete_no>_<seq>.png — düzenlenebilir).
  5. Kullanıcı istediği kadar tekrar eder.
  6. "🤖 AI'ya Gönder" → screenshot_subprocess ile claude'a iletilir.
  7. AISonuc modal pencerede gösterilir.
  8. Pencere kapanırken hasta klasörü silinir (geçici kayıt).

F9 hotkey: keyboard kütüphanesi (sadece bu oturum açıkken kayıtlı; Medula
odaktayken bile yakalanır — global hook).
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# YARDIMCILAR
# ──────────────────────────────────────────────────────────────────────

def _appdata_kok() -> Path:
    """%APPDATA%/BotanikKasa/ai_screenshots/ köküne mutlak yol."""
    base = os.environ.get("APPDATA") or str(Path.home())
    kok = Path(base) / "BotanikKasa" / "ai_screenshots"
    kok.mkdir(parents=True, exist_ok=True)
    return kok


def _dosya_adi_temizle(metin: str, max_uzunluk: int = 60) -> str:
    """Dosya adında geçersiz karakterleri ayıkla."""
    if not metin:
        return "isimsiz"
    # Windows + Linux için yasaklı karakterler
    temiz = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", metin)
    temiz = re.sub(r"\s+", "_", temiz).strip("._")
    return (temiz[:max_uzunluk] or "isimsiz")


def _hasta_id(hasta_bilgi: Dict[str, Any]) -> str:
    """Klasör adı için hasta tanımlayıcı (TC varsa onu, yoksa ad)."""
    tc = str(hasta_bilgi.get("tc") or "").strip()
    if tc:
        return _dosya_adi_temizle(tc, 20)
    ad = str(hasta_bilgi.get("ad") or "isimsiz").strip()
    return _dosya_adi_temizle(ad, 30)


# ──────────────────────────────────────────────────────────────────────
# BÖLGE SEÇİM OVERLAY
# ──────────────────────────────────────────────────────────────────────

class BolgeSecimOverlay(tk.Toplevel):
    """Tam ekran karartılmış overlay — kullanıcı mausla dikdörtgen çizer.

    Önce PIL ile primary monitor'ün screenshot'ı alınır, hafifçe karartılıp
    canvas'a basılır. Kullanıcı dikdörtgen çizer; release'te bbox saklanır
    ve pencere kapanır. ESC → iptal.

    Sonuçlar:
        self.bbox: (x1, y1, x2, y2) tuple veya None (iptal)
        self.ekran_resmi: PIL.Image — orijinal (karartılmamış) screenshot
    """

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        # PIL geç import (Pillow opsiyonel uyumluluk için)
        try:
            from PIL import Image, ImageEnhance, ImageGrab, ImageTk
        except ImportError as e:
            raise RuntimeError(
                "Pillow kurulu değil. Çözüm: pip install Pillow"
            ) from e

        # Önce screenshot al (overlay yokken)
        self.ekran_resmi: "Image.Image" = ImageGrab.grab(all_screens=False)
        sw, sh = self.ekran_resmi.size

        # Hafif karartılmış kopya — overlay arka planı
        karartilmis = ImageEnhance.Brightness(self.ekran_resmi).enhance(0.55)
        self._tk_img = ImageTk.PhotoImage(karartilmis)

        # Pencere kurulumu
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{sw}x{sh}+0+0")
        self.config(cursor="cross")

        self.canvas = tk.Canvas(
            self, width=sw, height=sh,
            highlightthickness=0, bd=0,
            bg="black",
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        # Bilgi yazısı
        self.canvas.create_text(
            sw // 2, 30,
            text="Mausla bir dikdörtgen çiz — ESC ile iptal",
            fill="white", font=("Segoe UI", 14, "bold"),
        )

        # Seçim durumu
        self.x1 = self.y1 = self.x2 = self.y2 = 0
        self.rect_id: Optional[int] = None
        self.bbox: Optional[tuple] = None

        self.canvas.bind("<Button-1>", self._mouse_down)
        self.canvas.bind("<B1-Motion>", self._mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)
        self.bind("<Escape>", lambda e: self._iptal())
        self.protocol("WM_DELETE_WINDOW", self._iptal)

        self.grab_set()
        self.focus_force()

    def _mouse_down(self, event):
        self.x1, self.y1 = event.x, event.y
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.x1, self.y1, self.x1, self.y1,
            outline="#00E5FF", width=2, dash=(4, 2),
        )

    def _mouse_drag(self, event):
        self.x2, self.y2 = event.x, event.y
        if self.rect_id is not None:
            self.canvas.coords(
                self.rect_id, self.x1, self.y1, self.x2, self.y2
            )

    def _mouse_up(self, event):
        self.x2, self.y2 = event.x, event.y
        x1, y1 = min(self.x1, self.x2), min(self.y1, self.y2)
        x2, y2 = max(self.x1, self.x2), max(self.y1, self.y2)
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            self._iptal()
            return
        self.bbox = (x1, y1, x2, y2)
        self.destroy()

    def _iptal(self):
        self.bbox = None
        self.destroy()


# ──────────────────────────────────────────────────────────────────────
# ETİKET DÜZENLEME POP-UP'I
# ──────────────────────────────────────────────────────────────────────

class EtiketOnayDialog(tk.Toplevel):
    """Screenshot çekildikten sonra etiket onaylama / düzenleme penceresi.

    Sonuç:
        self.etiket: str (Tamam'a basıldıysa) veya None (iptal)
    """

    def __init__(self, parent: tk.Misc, varsayilan_etiket: str,
                 thumbnail_img: Optional["Any"] = None):
        super().__init__(parent)
        self.title("Screenshot Etiketi")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.etiket: Optional[str] = None

        tk.Label(self, text="Bu görsel için etiket / dosya adı:",
                 font=("Segoe UI", 10, "bold")).pack(
            padx=14, pady=(12, 4), anchor="w")

        self.var_etiket = tk.StringVar(value=varsayilan_etiket)
        ent = tk.Entry(self, textvariable=self.var_etiket,
                       font=("Segoe UI", 10), width=60)
        ent.pack(padx=14, pady=(0, 4))
        ent.focus_set()
        ent.icursor("end")

        tk.Label(self, text="(.png otomatik eklenir, geçersiz karakterler "
                            "alt çizgiyle değiştirilir)",
                 font=("Segoe UI", 8), fg="#666").pack(
            padx=14, pady=(0, 8), anchor="w")

        # Thumbnail önizleme (varsa)
        if thumbnail_img is not None:
            try:
                tk.Label(self, image=thumbnail_img, bd=1, relief="solid").pack(
                    padx=14, pady=(0, 10))
                self._thumb_ref = thumbnail_img  # GC'den koru
            except Exception:
                pass

        btn_frame = tk.Frame(self)
        btn_frame.pack(padx=14, pady=(0, 12), fill="x")
        tk.Button(btn_frame, text="✓ Tamam", bg="#4CAF50", fg="white",
                  width=12, font=("Segoe UI", 9, "bold"),
                  command=self._tamam).pack(side="right", padx=(6, 0))
        tk.Button(btn_frame, text="İptal", width=10,
                  command=self._iptal).pack(side="right")

        self.bind("<Return>", lambda e: self._tamam())
        self.bind("<Escape>", lambda e: self._iptal())
        self.protocol("WM_DELETE_WINDOW", self._iptal)

        # Center on parent
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        except Exception:
            pass

    def _tamam(self):
        ham = self.var_etiket.get().strip()
        if not ham:
            messagebox.showwarning("Etiket Boş", "Bir etiket girin.",
                                    parent=self)
            return
        self.etiket = _dosya_adi_temizle(ham, 80)
        self.destroy()

    def _iptal(self):
        self.etiket = None
        self.destroy()


# ──────────────────────────────────────────────────────────────────────
# ANA TOPLAMA DIALOGU
# ──────────────────────────────────────────────────────────────────────

class ScreenshotSorguDialog(tk.Toplevel):
    """Screenshot toplama + AI'ya gönderim ana diyaloğu.

    Args:
        parent: Ana root.
        hasta_bilgi: {"ad": str, "tc": str, "yas": int, "cinsiyet": str}
        recete_bilgi: {"recete_no": str, "tarih": str, "ilac": str,
                        "rapor_kodu": str}
        ai_gonderim_callback: Opsiyonel — UI iş parçacığında çağrılır;
                              imzası: (hasta_bilgi, recete_bilgi,
                              gorsel_yollari, ek_soru, model, on_done).
                              Verilmezse varsayılan `screenshot_subprocess`
                              ile çağrı yapılır.
    """

    def __init__(
        self,
        parent: tk.Misc,
        hasta_bilgi: Dict[str, Any],
        recete_bilgi: Dict[str, Any],
        *,
        ai_gonderim_callback: Optional[Callable] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.hasta_bilgi = dict(hasta_bilgi or {})
        self.recete_bilgi = dict(recete_bilgi or {})
        self.ai_gonderim_callback = ai_gonderim_callback

        self.title("📸 Screenshot ile AI Sorgu")
        self.geometry("760x620")
        self.minsize(640, 520)
        self.transient(parent)
        # Topmost — Medula ön planda olsa bile diyalog ve liste görünür kalsın,
        # F9 ile peş peşe yakalama sırasında kullanıcı her seferinde sonucu
        # canlı görsün. (overlay/etiket dialog açıkken topmost geçici olarak
        # bizim üstümüze de çıkıyor, sorun değil.)
        self.attributes("-topmost", True)

        # Klasör hazırla
        zaman = datetime.now().strftime("%H%M%S")
        klasor_adi = f"{_hasta_id(self.hasta_bilgi)}_{zaman}"
        self.klasor: Path = _appdata_kok() / klasor_adi
        self.klasor.mkdir(parents=True, exist_ok=True)

        # Görsel listesi: [{"yol": Path, "etiket": str, "thumb_ref": PhotoImage}]
        self.gorseller: List[Dict[str, Any]] = []

        # Hotkey yönetimi
        self._hotkey_handle = None
        self._hotkey_var = None

        # F9 birden çok kez ard arda basılırsa tek instance overlay
        self._overlay_aktif = False

        self._kur_ui()
        self._hotkey_kaydet()

        self.protocol("WM_DELETE_WINDOW", self._iptal)
        self.bind("<Escape>", lambda e: self._iptal())

        # Kapanırken klasör temizliği
        self._temizlendi = False

    # ──────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────

    def _kur_ui(self):
        # Üst başlık
        ust = tk.Frame(self, bg="#0277BD", height=52)
        ust.pack(fill="x", side="top")
        ust.pack_propagate(False)
        tk.Label(
            ust, text="📸 Screenshot ile AI Sorgu — Medula Görsel Analizi",
            bg="#0277BD", fg="white",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=14, pady=12)

        # Hasta / reçete bilgisi
        bilgi = tk.LabelFrame(
            self, text="Hasta / Reçete Bağlamı (AI'ya bu bilgiyle gönderilir)",
            font=("Segoe UI", 9, "bold"), padx=10, pady=8,
        )
        bilgi.pack(fill="x", padx=10, pady=(10, 6))

        ad = self.hasta_bilgi.get("ad", "")
        tc = self.hasta_bilgi.get("tc", "")
        tc_kismi = tc[-4:] if tc and len(tc) >= 4 else ""
        yas = self.hasta_bilgi.get("yas", "")
        cins = self.hasta_bilgi.get("cinsiyet", "")
        rno = self.recete_bilgi.get("recete_no", "")
        rtarih = self.recete_bilgi.get("tarih", "")
        rilac = self.recete_bilgi.get("ilac", "")

        info_text = (
            f"Hasta: {ad}   TC: ****{tc_kismi}   "
            f"Yaş: {yas}   Cinsiyet: {cins}\n"
            f"Reçete: {rno}   Tarih: {rtarih}   İlaç: {rilac[:50]}"
        )
        tk.Label(bilgi, text=info_text, justify="left",
                 font=("Consolas", 9)).pack(anchor="w")

        # Ek soru / not alanı
        ek = tk.LabelFrame(
            self, text="Eczacı Notu / Ek Soru (opsiyonel)",
            font=("Segoe UI", 9, "bold"), padx=10, pady=6,
        )
        ek.pack(fill="x", padx=10, pady=(0, 6))
        self.txt_ek_soru = tk.Text(ek, height=2, font=("Segoe UI", 9),
                                    wrap="word")
        self.txt_ek_soru.pack(fill="x")

        # Model seçimi
        model_frame = tk.Frame(self)
        model_frame.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(model_frame, text="Model:",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self.var_model = tk.StringVar(value="sonnet")
        ttk.Combobox(model_frame, textvariable=self.var_model,
                     values=["sonnet", "opus", "haiku"],
                     state="readonly", width=12,
                     font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))
        tk.Label(model_frame,
                 text="  (Sonnet: hızlı+dengeli, Opus: en iyi, Haiku: en hızlı)",
                 font=("Segoe UI", 8), fg="#666").pack(side="left")

        # Aksiyon butonları
        aksiyon = tk.Frame(self, bg="#ECEFF1", pady=8)
        aksiyon.pack(fill="x", padx=10, pady=(0, 6))
        self.btn_ss = tk.Button(
            aksiyon, text="📷 Screenshot Al  (F9)",
            bg="#FF6F00", fg="white",
            activebackground="#E65100",
            font=("Segoe UI", 10, "bold"),
            padx=14, pady=6, cursor="hand2",
            command=self._screenshot_al,
        )
        self.btn_ss.pack(side="left", padx=(8, 4))

        self.btn_gonder = tk.Button(
            aksiyon, text="🤖 AI'ya Gönder",
            bg="#0277BD", fg="white",
            activebackground="#01579B",
            font=("Segoe UI", 10, "bold"),
            padx=14, pady=6, cursor="hand2",
            command=self._ai_gonder, state="disabled",
        )
        self.btn_gonder.pack(side="left", padx=4)

        tk.Button(aksiyon, text="❌ İptal",
                  font=("Segoe UI", 10), padx=12, pady=6,
                  command=self._iptal).pack(side="right", padx=8)

        # Liste başlığı
        liste_lbl = tk.LabelFrame(
            self, text="Yakalanan Ekran Görüntüleri (sıralı)",
            font=("Segoe UI", 9, "bold"), padx=6, pady=4,
        )
        liste_lbl.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # Scrollable thumbnail listesi
        kapsayici = tk.Frame(liste_lbl)
        kapsayici.pack(fill="both", expand=True)
        self.liste_canvas = tk.Canvas(kapsayici, bg="white",
                                       highlightthickness=0)
        scroll = tk.Scrollbar(kapsayici, orient="vertical",
                              command=self.liste_canvas.yview)
        self.liste_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.liste_canvas.pack(side="left", fill="both", expand=True)

        self.liste_ic = tk.Frame(self.liste_canvas, bg="white")
        self._liste_ic_id = self.liste_canvas.create_window(
            (0, 0), window=self.liste_ic, anchor="nw",
        )

        self.liste_ic.bind(
            "<Configure>",
            lambda e: self.liste_canvas.configure(
                scrollregion=self.liste_canvas.bbox("all")),
        )
        self.liste_canvas.bind(
            "<Configure>",
            lambda e: self.liste_canvas.itemconfig(
                self._liste_ic_id, width=e.width),
        )

        # Boş durum yazısı
        self._bos_lbl = tk.Label(
            self.liste_ic, bg="white", fg="#999",
            text="(Henüz screenshot yok. F9'a basın veya 'Screenshot Al' "
                 "butonuna tıklayın.)",
            font=("Segoe UI", 10, "italic"), pady=20,
        )
        self._bos_lbl.pack()

        # Durum çubuğu
        self.var_durum = tk.StringVar(
            value="Hazır. F9 ile veya 📷 butonu ile screenshot alabilirsiniz."
        )
        tk.Label(self, textvariable=self.var_durum,
                 anchor="w", bg="#263238", fg="white",
                 font=("Segoe UI", 9), padx=10, pady=4,
                 ).pack(fill="x", side="bottom")

    # ──────────────────────────────────────────────────────────
    # F9 HOTKEY
    # ──────────────────────────────────────────────────────────

    def _hotkey_kaydet(self):
        """F9 global hotkey'i kaydet (keyboard lib)."""
        try:
            import keyboard
        except ImportError:
            logger.warning(
                "keyboard kütüphanesi kurulu değil; F9 hotkey pasif. "
                "pip install keyboard"
            )
            self.var_durum.set(
                "⚠ keyboard kütüphanesi yok — F9 çalışmaz. "
                "Buton ile screenshot alın."
            )
            return

        def _f9_handler():
            # keyboard thread'inden tk thread'ine geç
            try:
                self.after(0, self._screenshot_al)
            except tk.TclError:
                pass  # pencere kapanmış olabilir

        try:
            self._hotkey_handle = keyboard.add_hotkey(
                "f9", _f9_handler, suppress=False,
            )
            logger.info("F9 hotkey kaydedildi: %s", self._hotkey_handle)
        except Exception as e:
            logger.warning("F9 hotkey kayıt başarısız: %s", e)
            self.var_durum.set(
                f"⚠ F9 hotkey kayıt başarısız ({type(e).__name__}). "
                "Buton ile screenshot alın."
            )

    def _hotkey_iptal(self):
        if self._hotkey_handle is None:
            return
        try:
            import keyboard
            keyboard.remove_hotkey(self._hotkey_handle)
            logger.info("F9 hotkey kaldırıldı")
        except Exception as e:
            logger.debug("F9 hotkey kaldırma hatası: %s", e)
        self._hotkey_handle = None

    # ──────────────────────────────────────────────────────────
    # SCREENSHOT AKIŞI
    # ──────────────────────────────────────────────────────────

    def _screenshot_al(self):
        """Diyaloğu gizle → overlay aç → bbox al → kaydet → diyaloğa dön."""
        if self._overlay_aktif:
            return  # zaten açık
        self._overlay_aktif = True
        try:
            self.withdraw()
            # Pencere yöneticisinin pencereyi gizlemesi için kısa bekleme
            self.update_idletasks()
            self.after(200, self._screenshot_overlay_ac)
        except tk.TclError:
            self._overlay_aktif = False

    def _screenshot_overlay_ac(self):
        try:
            overlay = BolgeSecimOverlay(self.parent)
        except RuntimeError as e:
            self._overlay_aktif = False
            self.deiconify()
            messagebox.showerror("Pillow Eksik", str(e), parent=self)
            return
        except Exception as e:
            self._overlay_aktif = False
            self.deiconify()
            logger.exception("Overlay açma hatası")
            messagebox.showerror(
                "Screenshot Hatası",
                f"Bölge seçim overlay'i açılamadı:\n{type(e).__name__}: {e}",
                parent=self,
            )
            return

        # Overlay modal; kullanıcı bbox seçene veya iptal edene kadar bekler
        self.parent.wait_window(overlay)
        self._overlay_aktif = False

        if overlay.bbox is None:
            # İptal edildi
            self.deiconify()
            self.lift()
            self.focus_force()
            self.var_durum.set("Screenshot iptal edildi.")
            return

        # Kırp + kaydet
        try:
            kirpilmis = overlay.ekran_resmi.crop(overlay.bbox)
        except Exception as e:
            self.deiconify()
            messagebox.showerror(
                "Kırpma Hatası", f"Görsel kırpılamadı: {e}", parent=self)
            return

        # Varsayılan etiket — ANINDA kaydet (kullanıcı isterse listeden
        # yeniden adlandırır). Eskiden burada modal popup vardı; Medula öne
        # gelmişken pop-up arkada kalıp kullanıcı görmediği için screenshot
        # silent şekilde kayboluyordu (kullanıcı şikayeti 2026-05-22).
        sira = len(self.gorseller) + 1
        ad = _dosya_adi_temizle(self.hasta_bilgi.get("ad", "hasta"), 30)
        rno = _dosya_adi_temizle(self.recete_bilgi.get("recete_no", ""), 20)
        varsayilan = f"{ad}_{rno}_{sira:02d}" if rno else f"{ad}_{sira:02d}"

        # Thumbnail önizleme
        try:
            from PIL import ImageTk
            thumb = kirpilmis.copy()
            thumb.thumbnail((300, 200))
            thumb_tk = ImageTk.PhotoImage(thumb)
        except Exception:
            thumb_tk = None

        # Kaydet — aynı isim varsa _2, _3 ekle
        dosya_yolu = self.klasor / f"{varsayilan}.png"
        i = 2
        while dosya_yolu.exists():
            dosya_yolu = self.klasor / f"{varsayilan}_{i}.png"
            i += 1

        try:
            kirpilmis.save(dosya_yolu, "PNG")
        except Exception as e:
            logger.exception("Screenshot kaydetme hatası")
            self.deiconify()
            messagebox.showerror(
                "Kaydetme Hatası",
                f"Dosya kaydedilemedi:\n{type(e).__name__}: {e}",
                parent=self,
            )
            return

        self.gorseller.append({
            "yol": dosya_yolu,
            "etiket": dosya_yolu.stem,  # uzantısız ad
            "thumb_ref": thumb_tk,
        })

        # Diyaloğu tekrar göster ve listeyi güncelle (Medula üstünde topmost
        # olduğu için kullanıcı sayacın arttığını anında görür).
        self.deiconify()
        self.lift()
        self._liste_yenile()
        self.btn_gonder.config(state="normal")
        self.var_durum.set(
            f"✓ Screenshot kaydedildi: {dosya_yolu.name}  "
            f"(toplam: {len(self.gorseller)})  —  F9 ile devam edebilirsiniz."
        )

    def _liste_yenile(self):
        """Thumbnail listesini yeniden çiz."""
        for w in self.liste_ic.winfo_children():
            w.destroy()

        if not self.gorseller:
            self._bos_lbl = tk.Label(
                self.liste_ic, bg="white", fg="#999",
                text="(Henüz screenshot yok.)",
                font=("Segoe UI", 10, "italic"), pady=20,
            )
            self._bos_lbl.pack()
            return

        for idx, g in enumerate(self.gorseller, 1):
            satir = tk.Frame(self.liste_ic, bg="white", bd=1, relief="solid")
            satir.pack(fill="x", padx=4, pady=3)

            # Thumbnail
            if g.get("thumb_ref") is not None:
                tk.Label(satir, image=g["thumb_ref"], bg="white").pack(
                    side="left", padx=4, pady=4)

            # Bilgi
            ic = tk.Frame(satir, bg="white")
            ic.pack(side="left", fill="both", expand=True, padx=6, pady=4)
            tk.Label(
                ic, text=f"#{idx}  {g['etiket']}.png",
                bg="white", font=("Segoe UI", 9, "bold"),
                anchor="w",
            ).pack(fill="x")
            try:
                boyut_kb = g["yol"].stat().st_size // 1024
            except Exception:
                boyut_kb = 0
            tk.Label(
                ic, text=f"{boyut_kb} KB   {g['yol']}",
                bg="white", fg="#666",
                font=("Segoe UI", 8),
                anchor="w",
            ).pack(fill="x")

            # Sil + Yeniden Adlandır butonları
            btn_kapsayici = tk.Frame(satir, bg="white")
            btn_kapsayici.pack(side="right", padx=6, pady=4)
            tk.Button(
                btn_kapsayici, text="✎ Ad",
                bg="#FFF9C4", fg="#5D4037",
                font=("Segoe UI", 9, "bold"), bd=1,
                padx=6, cursor="hand2",
                command=lambda i=idx - 1: self._gorseli_yeniden_adlandir(i),
            ).pack(side="top", fill="x", pady=(0, 2))
            tk.Button(
                btn_kapsayici, text="🗑 Sil",
                bg="#FFCDD2", fg="#B71C1C",
                font=("Segoe UI", 9, "bold"), bd=1,
                padx=6, cursor="hand2",
                command=lambda i=idx - 1: self._gorseli_sil(i),
            ).pack(side="top", fill="x")

    def _gorseli_sil(self, idx: int):
        if idx < 0 or idx >= len(self.gorseller):
            return
        g = self.gorseller.pop(idx)
        try:
            Path(g["yol"]).unlink(missing_ok=True)
        except Exception:
            pass
        self._liste_yenile()
        if not self.gorseller:
            self.btn_gonder.config(state="disabled")
        self.var_durum.set(f"Görsel silindi: {g['etiket']}.png")

    def _gorseli_yeniden_adlandir(self, idx: int):
        """Listedeki bir screenshot için etiket dialogunu aç ve dosyayı taşı."""
        if idx < 0 or idx >= len(self.gorseller):
            return
        g = self.gorseller[idx]
        eski_yol = Path(g["yol"])

        onay = EtiketOnayDialog(self, g["etiket"], thumbnail_img=g.get("thumb_ref"))
        # Etiket dialogu da topmost olsun ki Medula öne çıksa bile görünsün
        try:
            onay.attributes("-topmost", True)
        except Exception:
            pass
        self.wait_window(onay)

        if onay.etiket is None or onay.etiket == g["etiket"]:
            return  # iptal ya da değişiklik yok

        yeni_yol = self.klasor / f"{onay.etiket}.png"
        i = 2
        while yeni_yol.exists():
            yeni_yol = self.klasor / f"{onay.etiket}_{i}.png"
            i += 1

        try:
            eski_yol.rename(yeni_yol)
        except Exception as e:
            logger.exception("Yeniden adlandırma hatası")
            messagebox.showerror(
                "Yeniden Adlandırma Hatası",
                f"Dosya yeniden adlandırılamadı:\n{type(e).__name__}: {e}",
                parent=self,
            )
            return

        g["yol"] = yeni_yol
        g["etiket"] = yeni_yol.stem
        self._liste_yenile()
        self.var_durum.set(f"Yeniden adlandırıldı: {yeni_yol.name}")

    # ──────────────────────────────────────────────────────────
    # AI GÖNDERİM
    # ──────────────────────────────────────────────────────────

    def _ai_gonder(self):
        if not self.gorseller:
            messagebox.showinfo(
                "Screenshot Yok",
                "Önce en az bir screenshot ekleyin.", parent=self,
            )
            return

        # KVKK kontrolü
        try:
            from . import ayarlar as ai_ayarlar
            if not ai_ayarlar.kvkk_onayli_mi():
                messagebox.showwarning(
                    "KVKK Onayı Gerekli",
                    "AI sorgu için KVKK onayı verilmelidir.\n"
                    "AI Ayarlar penceresinden onaylayın.",
                    parent=self,
                )
                return
        except Exception:
            logger.debug("KVKK kontrol atlandı", exc_info=True)

        ek_soru = self.txt_ek_soru.get("1.0", "end").strip()
        model = self.var_model.get()
        yollar = [str(g["yol"]) for g in self.gorseller]

        # UI'yi kilitle
        self.btn_ss.config(state="disabled")
        self.btn_gonder.config(state="disabled", text="⏳ AI çalışıyor...")
        self.var_durum.set(
            f"⏳ Claude'a {len(yollar)} görsel gönderildi, cevap bekleniyor..."
        )
        self.update_idletasks()

        # Worker thread — subprocess bloklamasın
        threading.Thread(
            target=self._ai_worker,
            args=(yollar, ek_soru, model),
            daemon=True,
        ).start()

    def _ai_worker(self, yollar: List[str], ek_soru: str, model: str):
        """Arka planda subprocess'i çağırır; sonucu tk thread'ine taşır."""
        baslangic = time.time()
        try:
            if self.ai_gonderim_callback:
                sonuc = self.ai_gonderim_callback(
                    self.hasta_bilgi, self.recete_bilgi,
                    yollar, ek_soru, model,
                )
                cevap = None
            else:
                from . import screenshot_subprocess
                sonuc, cevap = screenshot_subprocess.screenshotlardan_kontrol_et(
                    self.hasta_bilgi, self.recete_bilgi, yollar,
                    ek_soru=ek_soru, model=model,
                )
        except Exception as e:
            logger.exception("Screenshot AI sorgu hatası")
            hata_metni = f"{type(e).__name__}: {e}"
            self.after(0, lambda: self._ai_hata_goster(hata_metni))
            return

        sure = int(time.time() - baslangic)
        self.after(0, lambda: self._ai_sonuc_goster(sonuc, cevap, sure))

    def _ai_hata_goster(self, mesaj: str):
        self.btn_ss.config(state="normal")
        self.btn_gonder.config(state="normal", text="🤖 AI'ya Gönder")
        self.var_durum.set(f"✗ AI sorgu hatası: {mesaj[:80]}")
        messagebox.showerror(
            "AI Sorgu Hatası",
            f"Claude'dan cevap alınamadı:\n\n{mesaj}",
            parent=self,
        )

    def _ai_sonuc_goster(self, sonuc, cevap, sure_sn: int):
        """Sonucu modal pencerede göster; kapatırken klasör silinir."""
        self.btn_ss.config(state="normal")
        self.btn_gonder.config(state="normal", text="🤖 AI'ya Gönder")
        self.var_durum.set(
            f"✓ AI sorgu tamamlandı ({sure_sn} sn) — sonuç: {sonuc.etiket}"
        )

        rapor = AISonucDialog(self, sonuc, cevap, sure_sn)
        self.wait_window(rapor)

        # Kullanıcı sonuç penceresini kapattı → klasörü temizle ve diyaloğu kapat
        self._iptal(temiz_kapanis=True)

    # ──────────────────────────────────────────────────────────
    # KAPANIŞ
    # ──────────────────────────────────────────────────────────

    def _iptal(self, temiz_kapanis: bool = False):
        if self._temizlendi:
            return
        # Onay (eğer screenshot varsa ve henüz AI'ya gönderilmediyse)
        if not temiz_kapanis and self.gorseller:
            cevap = messagebox.askyesno(
                "Çıkış Onayı",
                f"{len(self.gorseller)} kaydedilmiş screenshot silinecek.\n\n"
                "Devam edilsin mi?",
                parent=self,
            )
            if not cevap:
                return

        self._hotkey_iptal()

        # Klasörü sil
        try:
            if self.klasor.exists():
                shutil.rmtree(self.klasor, ignore_errors=True)
                logger.info("Screenshot klasörü silindi: %s", self.klasor)
        except Exception as e:
            logger.warning("Klasör temizleme hatası: %s", e)

        self._temizlendi = True
        try:
            self.destroy()
        except tk.TclError:
            pass


# ──────────────────────────────────────────────────────────────────────
# AI SONUÇ GÖSTERİM DİYALOĞU
# ──────────────────────────────────────────────────────────────────────

class AISonucDialog(tk.Toplevel):
    """Screenshot AI sonucunu modal pencerede göster."""

    def __init__(self, parent: tk.Misc, sonuc, cevap, sure_sn: int):
        super().__init__(parent)
        self.title(f"🤖 AI Sonuç — {sonuc.etiket}")
        self.geometry("780x600")
        self.minsize(560, 420)
        self.transient(parent)
        self.grab_set()

        renk_bg = {
            "yesil": "#4CAF50",
            "kirmizi": "#D32F2F",
            "sari": "#FBC02D",
            "turuncu": "#F57C00",
            "beyaz": "#607D8B",
        }.get(sonuc.renk, "#607D8B")

        # Üst bant — büyük etiket
        ust = tk.Frame(self, bg=renk_bg, height=64)
        ust.pack(fill="x", side="top")
        ust.pack_propagate(False)
        tk.Label(ust, text=sonuc.etiket, bg=renk_bg, fg="white",
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=16,
                                                       pady=14)
        guven_yzd = int((sonuc.guven_skoru or 0) * 100)
        tk.Label(
            ust,
            text=f"Güven: %{guven_yzd}   Süre: {sure_sn} sn",
            bg=renk_bg, fg="white", font=("Segoe UI", 10),
        ).pack(side="right", padx=16, pady=18)

        # Açıklama metni
        cerceve = tk.Frame(self, padx=10, pady=10)
        cerceve.pack(fill="both", expand=True)

        txt = tk.Text(cerceve, wrap="word", font=("Segoe UI", 10), bd=1,
                       relief="solid")
        scr = tk.Scrollbar(cerceve, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=scr.set)
        scr.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        txt.insert("end", sonuc.aciklama_metni() or "(açıklama yok)")
        if sonuc.hata:
            txt.insert("end", f"\n\n⚠ Hata: {sonuc.hata}")
        txt.config(state="disabled")

        # Alt bilgi
        alt = tk.Frame(self, bg="#ECEFF1", padx=10, pady=8)
        alt.pack(fill="x", side="bottom")

        token_metin = ""
        if cevap is not None:
            token_metin = (
                f"Tokens: in={getattr(cevap, 'input_tokens', 0)} / "
                f"out={getattr(cevap, 'output_tokens', 0)}"
            )
            maliyet = getattr(cevap, "total_cost_usd", 0.0) or 0.0
            if maliyet > 0:
                token_metin += f"   Maliyet: ${maliyet:.4f}"
        if token_metin:
            tk.Label(alt, text=token_metin, bg="#ECEFF1",
                     font=("Segoe UI", 8), fg="#37474F").pack(side="left")

        tk.Button(alt, text="Kapat", font=("Segoe UI", 10, "bold"),
                  padx=14, command=self.destroy).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)


# ──────────────────────────────────────────────────────────────────────
# DIŞARI AÇILAN YARDIMCI
# ──────────────────────────────────────────────────────────────────────

def ac(
    parent: tk.Misc,
    hasta_bilgi: Dict[str, Any],
    recete_bilgi: Dict[str, Any],
    **kwargs,
) -> ScreenshotSorguDialog:
    """Diyaloğu aç ve referansını döndür."""
    return ScreenshotSorguDialog(
        parent, hasta_bilgi, recete_bilgi, **kwargs,
    )
