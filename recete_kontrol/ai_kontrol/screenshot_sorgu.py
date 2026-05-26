"""Screenshot yakalama + gözden geçirme — AI Kontrol entegrasyonu için.

Mimari (2026-05-23 refactor):
  • F2 hotkey GUI seviyesinde kayıtlı (aylik_recete_sorgu_gui.py); bu modül
    sadece bölge seçim overlay'i + kaydetme fonksiyonu sağlar.
  • Screenshot'lar SATIR BAZLI bir klasöre yazılır; AI KONTROL butonu
    bunları paketle birlikte Claude'a gönderir.
  • Bu modüldeki ScreenshotReviewDialog: kullanıcı SS butonuna basınca
    biriken görselleri görür, rename/sil yapar. AI'ya gönderim yok.

İçindekiler:
  • _appdata_kok / _dosya_adi_temizle — yardımcılar
  • BolgeSecimOverlay — fullscreen darkened maus dikdörtgen seçici
  • yakala_ve_kaydet(parent, target_dir, default_name) → Path | None
        F2 handler'ının kullanacağı atomik fonksiyon
  • ScreenshotReviewDialog — toplanan görselleri yöneten modal pencere
"""
from __future__ import annotations

import logging
import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
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
    temiz = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", metin)
    temiz = re.sub(r"\s+", "_", temiz).strip("._")
    return (temiz[:max_uzunluk] or "isimsiz")


def satir_klasoru_uret(kok: Optional[Path] = None,
                       hasta_tc: str = "",
                       recete_no: str = "") -> Path:
    """Satır-bazlı screenshot klasörünü hesapla (oluşturma garantili).

    Format: <kok>/<tc_or_anonim>_<recete_no>/
    Aynı reçeteye sonradan eklenen görseller aynı klasöre düşer.
    """
    if kok is None:
        kok = _appdata_kok()
    tc = _dosya_adi_temizle(hasta_tc or "anonim", 20)
    rno = _dosya_adi_temizle(recete_no or "norec", 20)
    klasor = kok / f"{tc}_{rno}"
    klasor.mkdir(parents=True, exist_ok=True)
    return klasor


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
        try:
            from PIL import Image, ImageEnhance, ImageGrab, ImageTk
        except ImportError as e:
            raise RuntimeError(
                "Pillow kurulu değil. Çözüm: pip install Pillow"
            ) from e

        self.ekran_resmi: "Image.Image" = ImageGrab.grab(all_screens=False)
        sw, sh = self.ekran_resmi.size

        karartilmis = ImageEnhance.Brightness(self.ekran_resmi).enhance(0.55)
        self._tk_img = ImageTk.PhotoImage(karartilmis)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{sw}x{sh}+0+0")
        self.config(cursor="cross")

        self.canvas = tk.Canvas(
            self, width=sw, height=sh,
            highlightthickness=0, bd=0, bg="black",
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
        self.canvas.create_text(
            sw // 2, 30,
            text="Mausla bir dikdörtgen çiz — ESC ile iptal",
            fill="white", font=("Segoe UI", 14, "bold"),
        )

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
# ATOMİK YAKALAMA FONKSİYONU — F2 handler bunu çağırır
# ──────────────────────────────────────────────────────────────────────

def yakala_ve_kaydet(
    parent: tk.Misc,
    target_dir: Path,
    default_name: str,
) -> Optional[Path]:
    """Bölge seçim overlay → kırp → PNG kaydet → mutlak yol döndür.

    Args:
        parent: tk root (overlay'in parent'ı)
        target_dir: klasör (mevcut değilse oluşturulur)
        default_name: dosya adı (uzantısız); .png otomatik eklenir; çakışma
                      olursa _2, _3 suffix

    Returns:
        Kaydedilen dosyanın Path'i, ya da iptal/hata durumunda None.
    """
    try:
        overlay = BolgeSecimOverlay(parent)
    except RuntimeError as e:
        messagebox.showerror("Pillow Eksik", str(e), parent=parent)
        return None
    except Exception as e:
        logger.exception("Overlay açma hatası")
        messagebox.showerror(
            "Screenshot Hatası",
            f"Bölge seçim overlay'i açılamadı:\n{type(e).__name__}: {e}",
            parent=parent,
        )
        return None

    parent.wait_window(overlay)

    if overlay.bbox is None:
        return None

    try:
        kirpilmis = overlay.ekran_resmi.crop(overlay.bbox)
    except Exception as e:
        messagebox.showerror("Kırpma Hatası",
                             f"Görsel kırpılamadı: {e}", parent=parent)
        return None

    target_dir.mkdir(parents=True, exist_ok=True)
    temiz_ad = _dosya_adi_temizle(default_name, 80) or "isimsiz"
    yol = target_dir / f"{temiz_ad}.png"
    i = 2
    while yol.exists():
        yol = target_dir / f"{temiz_ad}_{i}.png"
        i += 1

    try:
        kirpilmis.save(yol, "PNG")
        logger.info("Screenshot kaydedildi: %s", yol)
        return yol
    except Exception as e:
        logger.exception("Screenshot kaydetme hatası")
        messagebox.showerror(
            "Kaydetme Hatası",
            f"Dosya kaydedilemedi:\n{type(e).__name__}: {e}",
            parent=parent,
        )
        return None


# ──────────────────────────────────────────────────────────────────────
# REVIEW DIALOG — biriken screenshot'ları yönetme (rename/sil)
# ──────────────────────────────────────────────────────────────────────

class ScreenshotReviewDialog(tk.Toplevel):
    """Bir satıra ait biriken screenshot'ları gözden geçir + yönet.

    AI'ya gönderim BU dialogdan yapılmaz — kullanıcı dialogu kapatır,
    ardından AI KONTROL butonuna basar; satırda screenshot varsa o akış
    multimodal subprocess'e router'lar.

    Args:
        parent: ana root
        hasta_ad / recete_no / tarih / ilac: bilgi başlığı için
        yollar: List[Path] — değişkenlere referans (değişimler caller'a
                yansır; on_degisti callback ile bildirilir)
        on_degisti: Callable[[], None] — liste değiştiğinde GUI'nin
                    sayaç vs. güncelleyebilmesi için
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        hasta_ad: str = "",
        recete_no: str = "",
        tarih: str = "",
        ilac: str = "",
        yollar: List[Path],
        on_degisti: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.title("📸 Toplanan Screenshot'lar")
        self.geometry("760x560")
        self.minsize(560, 420)
        self.transient(parent)
        self.attributes("-topmost", True)

        self.yollar = yollar
        self.on_degisti = on_degisti

        # Üst başlık
        ust = tk.Frame(self, bg="#0277BD", height=48)
        ust.pack(fill="x", side="top")
        ust.pack_propagate(False)
        self.lbl_baslik = tk.Label(
            ust, text=f"Toplanan Görseller ({len(yollar)})",
            bg="#0277BD", fg="white", font=("Segoe UI", 12, "bold"),
        )
        self.lbl_baslik.pack(side="left", padx=14, pady=10)

        # Hasta bilgi
        bilgi = tk.LabelFrame(
            self, text="Reçete Bağlamı (AI'a otomatik gönderilir)",
            font=("Segoe UI", 9, "bold"), padx=10, pady=6,
        )
        bilgi.pack(fill="x", padx=10, pady=(10, 4))
        bilgi_metin = (
            f"Hasta: {hasta_ad}   Reçete: {recete_no}   "
            f"Tarih: {tarih}   İlaç: {ilac[:50]}"
        )
        tk.Label(bilgi, text=bilgi_metin, justify="left",
                 font=("Consolas", 9)).pack(anchor="w")

        # Açıklama
        tk.Label(
            self,
            text="ℹ AI'ya göndermek için bu pencereyi kapatıp "
                 "🤖 AI KONTROL butonuna basın — Botanik DB verisi + "
                 "screenshot'lar birlikte gönderilir.",
            font=("Segoe UI", 9), fg="#0277BD", wraplength=720,
            anchor="w", justify="left", padx=10,
        ).pack(fill="x", padx=10, pady=(0, 6))

        # Liste
        liste_lbl = tk.LabelFrame(
            self, text="Görseller",
            font=("Segoe UI", 9, "bold"), padx=6, pady=4,
        )
        liste_lbl.pack(fill="both", expand=True, padx=10, pady=(0, 6))

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

        # Thumbnail referansları GC'den korunsun
        self._thumb_refs: List[Any] = []

        # Alt aksiyon
        alt = tk.Frame(self, bg="#ECEFF1", pady=8)
        alt.pack(fill="x", side="bottom")
        tk.Button(alt, text="🗑 Tümünü Sil",
                  bg="#FFCDD2", fg="#B71C1C",
                  font=("Segoe UI", 9, "bold"), padx=10,
                  command=self._tumunu_sil).pack(side="left", padx=10)
        tk.Button(alt, text="Kapat", font=("Segoe UI", 10, "bold"),
                  padx=14, command=self.destroy).pack(side="right", padx=10)

        self._liste_yenile()

        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _liste_yenile(self):
        for w in self.liste_ic.winfo_children():
            w.destroy()
        self._thumb_refs.clear()

        self.lbl_baslik.config(
            text=f"Toplanan Görseller ({len(self.yollar)})"
        )

        if not self.yollar:
            tk.Label(
                self.liste_ic, bg="white", fg="#999",
                text="(Henüz screenshot yok. Pencereyi kapatın, "
                     "checkbox açıkken F2 ile yakalayın.)",
                font=("Segoe UI", 10, "italic"), pady=20,
            ).pack()
            return

        try:
            from PIL import Image, ImageTk
        except ImportError:
            Image = ImageTk = None  # type: ignore

        for idx, yol in enumerate(self.yollar, 1):
            satir = tk.Frame(self.liste_ic, bg="white", bd=1, relief="solid")
            satir.pack(fill="x", padx=4, pady=3)

            # Thumbnail
            if ImageTk is not None:
                try:
                    img = Image.open(yol)
                    img.thumbnail((280, 180))
                    th = ImageTk.PhotoImage(img)
                    self._thumb_refs.append(th)
                    tk.Label(satir, image=th, bg="white").pack(
                        side="left", padx=4, pady=4)
                except Exception:
                    pass

            ic = tk.Frame(satir, bg="white")
            ic.pack(side="left", fill="both", expand=True, padx=6, pady=4)
            tk.Label(
                ic, text=f"#{idx}  {yol.name}",
                bg="white", font=("Segoe UI", 9, "bold"), anchor="w",
            ).pack(fill="x")
            try:
                boyut_kb = yol.stat().st_size // 1024
            except Exception:
                boyut_kb = 0
            tk.Label(
                ic, text=f"{boyut_kb} KB   {yol}",
                bg="white", fg="#666",
                font=("Segoe UI", 8), anchor="w",
            ).pack(fill="x")

            btn_kap = tk.Frame(satir, bg="white")
            btn_kap.pack(side="right", padx=6, pady=4)
            tk.Button(
                btn_kap, text="✎ Ad",
                bg="#FFF9C4", fg="#5D4037",
                font=("Segoe UI", 9, "bold"), bd=1, padx=6, cursor="hand2",
                command=lambda i=idx - 1: self._yeniden_adlandir(i),
            ).pack(side="top", fill="x", pady=(0, 2))
            tk.Button(
                btn_kap, text="🗑 Sil",
                bg="#FFCDD2", fg="#B71C1C",
                font=("Segoe UI", 9, "bold"), bd=1, padx=6, cursor="hand2",
                command=lambda i=idx - 1: self._sil(i),
            ).pack(side="top", fill="x")

    def _sil(self, idx: int):
        if idx < 0 or idx >= len(self.yollar):
            return
        yol = self.yollar.pop(idx)
        try:
            yol.unlink(missing_ok=True)
        except Exception:
            pass
        self._liste_yenile()
        if self.on_degisti:
            self.on_degisti()

    def _tumunu_sil(self):
        if not self.yollar:
            return
        if not messagebox.askyesno(
            "Onay",
            f"{len(self.yollar)} screenshot silinecek. Emin misiniz?",
            parent=self,
        ):
            return
        for y in list(self.yollar):
            try:
                y.unlink(missing_ok=True)
            except Exception:
                pass
        self.yollar.clear()
        self._liste_yenile()
        if self.on_degisti:
            self.on_degisti()

    def _yeniden_adlandir(self, idx: int):
        if idx < 0 or idx >= len(self.yollar):
            return
        eski = self.yollar[idx]
        yeni_ad = self._etiket_iste(eski.stem)
        if not yeni_ad or yeni_ad == eski.stem:
            return
        yeni = eski.parent / f"{_dosya_adi_temizle(yeni_ad, 80)}.png"
        i = 2
        while yeni.exists():
            yeni = eski.parent / f"{_dosya_adi_temizle(yeni_ad, 80)}_{i}.png"
            i += 1
        try:
            eski.rename(yeni)
        except Exception as e:
            messagebox.showerror("Yeniden Adlandırma",
                                 f"Hata: {e}", parent=self)
            return
        self.yollar[idx] = yeni
        self._liste_yenile()
        if self.on_degisti:
            self.on_degisti()

    def _etiket_iste(self, varsayilan: str) -> Optional[str]:
        """Basit metin giriş dialogu."""
        dlg = tk.Toplevel(self)
        dlg.title("Yeniden Adlandır")
        dlg.transient(self)
        dlg.grab_set()
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)

        sonuc: Dict[str, Optional[str]] = {"v": None}

        tk.Label(dlg, text="Yeni dosya adı (uzantısız):",
                 font=("Segoe UI", 10)).pack(padx=14, pady=(12, 4),
                                              anchor="w")
        var = tk.StringVar(value=varsayilan)
        ent = tk.Entry(dlg, textvariable=var, width=60,
                       font=("Segoe UI", 10))
        ent.pack(padx=14, pady=(0, 8))
        ent.focus_set()
        ent.icursor("end")
        ent.select_range(0, "end")

        def _ok():
            sonuc["v"] = var.get().strip() or None
            dlg.destroy()

        def _iptal():
            sonuc["v"] = None
            dlg.destroy()

        frm = tk.Frame(dlg)
        frm.pack(padx=14, pady=(0, 12), fill="x")
        tk.Button(frm, text="Tamam", bg="#4CAF50", fg="white",
                  width=10, font=("Segoe UI", 9, "bold"),
                  command=_ok).pack(side="right", padx=(6, 0))
        tk.Button(frm, text="İptal", width=10,
                  command=_iptal).pack(side="right")

        dlg.bind("<Return>", lambda e: _ok())
        dlg.bind("<Escape>", lambda e: _iptal())
        self.wait_window(dlg)
        return sonuc["v"]


# ──────────────────────────────────────────────────────────────────────
# DIŞARI AÇILAN YARDIMCILAR
# ──────────────────────────────────────────────────────────────────────

def goster(
    parent: tk.Misc,
    *,
    hasta_ad: str = "",
    recete_no: str = "",
    tarih: str = "",
    ilac: str = "",
    yollar: List[Path],
    on_degisti: Optional[Callable[[], None]] = None,
) -> ScreenshotReviewDialog:
    """Review dialogunu aç ve referansını döndür."""
    return ScreenshotReviewDialog(
        parent,
        hasta_ad=hasta_ad,
        recete_no=recete_no,
        tarih=tarih,
        ilac=ilac,
        yollar=yollar,
        on_degisti=on_degisti,
    )
