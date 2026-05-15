"""
Pencere Yerleşim Yöneticisi
---------------------------
MEDULA (BotanikEOS) ve Hasta Takip penceresinin mevcut konum/boyutunu
kaydeder ve program başlangıcında geri yükler.

JSON dosyası: pencere_yerlesim.json (script dizininde).
"""

import json
import logging
import os
from typing import Optional

try:
    import win32gui
    import win32con
    _WIN32_VAR = True
except ImportError:
    _WIN32_VAR = False

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_YOLU = os.path.join(_SCRIPT_DIR, "pencere_yerlesim.json")


def _medula_hwnd_bul(strict: bool = False) -> Optional[int]:
    """MEDULA / BotanikEOS ana penceresinin HWND'sini döndürür.

    Title'da "MEDULA" geçen ilk görünür pencere; bulunamazsa
    "BotanikEOS" + "(T)" içeren pencere aranır.

    strict=True ise BotanikEOS fallback'i devre dışı — sadece title'da
    "MEDULA" geçen pencere döndürülür. Medula-spesifik işlemlerde
    (keepalive, F5, Giriş butonu tıklama) Botanik EOS'a yanlışlıkla
    tıklama yapılmaması için kullanılır.
    """
    if not _WIN32_VAR:
        return None

    adaylar_medula = []
    adaylar_eos = []

    def _enum(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd) or ""
            cls = win32gui.GetClassName(hwnd) or ""
            # Dialog'ları dışla (ör. 'MEDULA Yok' adlı hata kutusu)
            if cls.startswith("#32770"):
                return True
            # Sadece WinForms ana pencere kabul (BotanikEOS/MEDULA)
            if not cls.startswith("WindowsForms"):
                return True
            if "MEDULA" in title:
                adaylar_medula.append(hwnd)
            elif "BotanikEOS" in title and "(T)" in title:
                parcalar = title.replace("(T)", "").strip().split()
                if len(parcalar) >= 3:
                    adaylar_eos.append(hwnd)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_enum, None)

    if adaylar_medula:
        return adaylar_medula[0]
    if strict:
        return None
    if adaylar_eos:
        return adaylar_eos[0]
    return None


def _hwnd_rect(hwnd: int):
    """HWND için (x, y, w, h) döndürür; maximize ise restore edilmiş değer."""
    try:
        placement = win32gui.GetWindowPlacement(hwnd)
        # placement[4] = normal (restored) position: (L, T, R, B)
        if placement[1] == win32con.SW_SHOWMAXIMIZED:
            l, t, r, b = placement[4]
        else:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
        return int(l), int(t), int(r - l), int(b - t)
    except Exception as e:
        logger.debug(f"_hwnd_rect hatası: {e}")
        return None


def yerlesim_yukle() -> dict:
    """JSON'daki yerleşim ayarlarını döndür; dosya yoksa {} döner."""
    if not os.path.exists(JSON_YOLU):
        return {}
    try:
        with open(JSON_YOLU, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        logger.error(f"Yerleşim JSON okunamadı: {e}")
        return {}


def yerlesim_kaydet(data: dict) -> bool:
    """Verilen dict'i JSON'a yaz."""
    try:
        with open(JSON_YOLU, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Pencere yerleşimi kaydedildi: {JSON_YOLU}")
        return True
    except Exception as e:
        logger.error(f"Yerleşim kaydedilemedi: {e}")
        return False


def mevcut_yerlesimi_yakala(tk_root=None) -> dict:
    """Anki MEDULA ve (varsa) Hasta Takip (tk_root) yerleşimini döndür.

    tk_root: tkinter.Tk veya Toplevel; None ise sadece MEDULA yakalanır.
    Kaydetmez — sadece dict döndürür.
    """
    data = yerlesim_yukle()

    # MEDULA
    hwnd = _medula_hwnd_bul()
    if hwnd:
        rect = _hwnd_rect(hwnd)
        if rect:
            x, y, w, h = rect
            data["medula"] = {"x": x, "y": y, "width": w, "height": h}
            logger.info(f"MEDULA yerleşimi yakalandı: {x},{y} {w}x{h}")
    else:
        logger.warning("MEDULA penceresi bulunamadı — yerleşim güncellenmedi")

    # Hasta Takip (tkinter)
    if tk_root is not None:
        try:
            tk_root.update_idletasks()
            x = tk_root.winfo_x()
            y = tk_root.winfo_y()
            w = tk_root.winfo_width()
            h = tk_root.winfo_height()
            data["hasta_takip"] = {"x": x, "y": y, "width": w, "height": h}
            logger.info(f"Hasta Takip yerleşimi yakalandı: {x},{y} {w}x{h}")
        except Exception as e:
            logger.error(f"Hasta Takip yerleşimi okunamadı: {e}")

    return data


def yerlesimi_kaydet_simdi(tk_root=None) -> bool:
    """Anki yerleşimi yakala ve JSON'a yaz. Tek adımda kaydetmek için."""
    data = mevcut_yerlesimi_yakala(tk_root=tk_root)
    if not data:
        return False
    return yerlesim_kaydet(data)


def medulaya_uygula(hwnd: Optional[int] = None) -> bool:
    """Kaydedilmiş MEDULA yerleşimini uygula.

    hwnd verilmezse _medula_hwnd_bul() ile aranır.
    Kayıtlı yerleşim yoksa False döner (çağıran fallback kullanmalı).
    """
    if not _WIN32_VAR:
        return False

    data = yerlesim_yukle().get("medula")
    if not data:
        return False

    if hwnd is None:
        hwnd = _medula_hwnd_bul()
    if not hwnd:
        logger.warning("MEDULA HWND bulunamadı — yerleşim uygulanamadı")
        return False

    try:
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMAXIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception as e:
        logger.debug(f"MEDULA restore hatası: {e}")

    try:
        win32gui.MoveWindow(
            hwnd,
            int(data["x"]), int(data["y"]),
            int(data["width"]), int(data["height"]),
            True,
        )
        logger.info(
            f"✓ MEDULA yerleşimi uygulandı: "
            f"{data['x']},{data['y']} {data['width']}x{data['height']}"
        )
        return True
    except Exception as e:
        logger.error(f"MEDULA MoveWindow hatası: {e}")
        return False


def hasta_takibe_uygula(tk_root) -> bool:
    """Kaydedilmiş Hasta Takip yerleşimini tkinter penceresine uygula."""
    data = yerlesim_yukle().get("hasta_takip")
    if not data or tk_root is None:
        return False
    try:
        x = int(data["x"])
        y = int(data["y"])
        w = int(data["width"])
        h = int(data["height"])
        tk_root.geometry(f"{w}x{h}+{x}+{y}")
        logger.info(f"✓ Hasta Takip yerleşimi uygulandı: {x},{y} {w}x{h}")
        return True
    except Exception as e:
        logger.error(f"Hasta Takip geometry hatası: {e}")
        return False
