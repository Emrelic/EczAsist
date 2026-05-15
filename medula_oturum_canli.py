"""
MEDULA Oturum Canlı Tutucu
--------------------------
MEDULA penceresine yapılan tıklamaları dinler.
Belirli süre (varsayılan 110 sn = 1 dk 50 sn) boyunca MEDULA içinde
tıklama olmazsa:
  - MEDULA penceresindeki "Giriş" butonuna pywinauto invoke ile
    sessizce tıklar (foreground'a alınmaz, kullanıcının çalışması
    kesintiye uğramaz).

ÖNEMLİ: Pencere tarama strict=True yapılır — Medula yoksa hiçbir şey
yapılmaz. Botanik EOS ana penceresine yanlışlıkla F5/tıklama gönderme
bug'ı (fallback yoluyla) bu sayede engellenir.
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

IDLE_ESIK_SN = 110           # 1 dakika 50 saniye
TARAMA_ARALIK_SN = 2


class MedulaOturumCanli:
    def __init__(self):
        self._calisiyor = False
        self._worker: Optional[threading.Thread] = None
        self._listener = None
        self._son_tiklama_ts = time.monotonic()
        self._lock = threading.Lock()
        self._son_yenileme_ts = 0.0

    # ---------------------------------------------------------------- helpers

    def _medula_rect(self):
        """MEDULA penceresinin ekran koordinatlarındaki rect'ini döndür."""
        try:
            import win32gui
            from pencere_yerlesim import _medula_hwnd_bul
            hwnd = _medula_hwnd_bul(strict=True)
            if not hwnd:
                return None
            return win32gui.GetWindowRect(hwnd)  # (L, T, R, B)
        except Exception as e:
            logger.debug(f"MEDULA rect hatası: {e}")
            return None

    def _nokta_medula_icinde_mi(self, x: int, y: int) -> bool:
        rect = self._medula_rect()
        if not rect:
            return False
        l, t, r, b = rect
        return l <= x <= r and t <= y <= b

    # ---------------------------------------------------------------- listener

    def _on_click(self, x, y, button, pressed):
        if not pressed or not self._calisiyor:
            return
        try:
            if self._nokta_medula_icinde_mi(int(x), int(y)):
                with self._lock:
                    self._son_tiklama_ts = time.monotonic()
                logger.debug(f"[OTURUM] MEDULA tıklaması: {x},{y}")
        except Exception as e:
            logger.debug(f"_on_click hata: {e}")

    # ---------------------------------------------------------------- refresh

    def _medula_hwnd(self):
        """MEDULA ana HWND'sini bul — strict (Botanik EOS fallback YOK)."""
        try:
            from pencere_yerlesim import _medula_hwnd_bul
            return _medula_hwnd_bul(strict=True)
        except Exception:
            return None

    def _giris_butonu_tikla(self, hwnd) -> bool:
        """Medula penceresindeki 'Giriş' butonuna pywinauto invoke ile tıkla.

        SALT NAVİGASYON — veri değiştirmez. Foreground'a alınmaz,
        kullanıcı başka modülde çalışıyor olabilir (sessiz).
        """
        try:
            from pywinauto import Application
        except Exception as e:
            logger.error(f"[OTURUM] pywinauto yok: {e}")
            return False

        try:
            app = Application(backend="uia").connect(handle=hwnd)
            w = app.window(handle=hwnd)
        except Exception as e:
            logger.debug(f"[OTURUM] UIA connect hatası: {e}")
            return False

        try:
            for b in w.descendants(control_type="Button"):
                try:
                    cap = (b.window_text() or "").strip().replace("&", "")
                    # WinForms accelerator '&' temizlendi; Türkçe büyük/küçük tolere
                    if cap == "Giriş" or cap.lower() == "giriş":
                        try:
                            b.invoke()
                            logger.info("[OTURUM] ✓ Medula 'Giriş' invoke edildi")
                            return True
                        except Exception as e:
                            logger.debug(f"[OTURUM] invoke hatası: {e}")
                            # invoke desteklenmiyorsa click_input (gerçek mouse)
                            try:
                                b.click_input()
                                logger.info(
                                    "[OTURUM] ✓ Medula 'Giriş' click_input edildi"
                                )
                                return True
                            except Exception as e2:
                                logger.debug(f"[OTURUM] click_input hatası: {e2}")
                                return False
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[OTURUM] Buton tarama hatası: {e}")
            return False

        logger.warning("[OTURUM] Medula penceresinde 'Giriş' butonu bulunamadı")
        return False

    def _oturumu_yenile(self):
        """Medula 'Giriş' butonuna sessizce tıklayarak oturumu canlı tutar.

        Botanik EOS fallback'i kapatıldığı için Medula penceresi yoksa
        hiçbir şey yapılmaz (bu, daha önce Botanik EOS'a F5/tıklama
        gönderilen bug'ı engeller).
        """
        logger.info(f"[OTURUM] {IDLE_ESIK_SN}s idle — Medula Giriş'e tıklanıyor")
        try:
            hwnd = self._medula_hwnd()
            if not hwnd:
                logger.warning(
                    "[OTURUM] Medula penceresi bulunamadı — atlanıyor "
                    "(Botanik EOS'a tıklanmaz)"
                )
                return

            if self._giris_butonu_tikla(hwnd):
                self._son_yenileme_ts = time.monotonic()
        except Exception as e:
            logger.error(f"[OTURUM] Yenileme hatası: {e}", exc_info=True)

    # ---------------------------------------------------------------- loop

    def _dongu(self):
        # Bu thread'de pywinauto.Application (UIA backend) çağrılabilir → COM init
        com_init_edildi = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_init_edildi = True
        except Exception as e:
            logger.debug(f"[OTURUM] CoInitialize hatası: {e}")

        try:
            while self._calisiyor:
                try:
                    with self._lock:
                        gecen = time.monotonic() - self._son_tiklama_ts
                    if gecen >= IDLE_ESIK_SN:
                        self._oturumu_yenile()
                        with self._lock:
                            self._son_tiklama_ts = time.monotonic()
                except Exception as e:
                    logger.error(f"[OTURUM] Döngü hatası: {e}", exc_info=True)
                time.sleep(TARAMA_ARALIK_SN)
        finally:
            if com_init_edildi:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    # ---------------------------------------------------------------- api

    def aktif_mi(self) -> bool:
        return self._calisiyor

    def idle_saniye(self) -> float:
        with self._lock:
            return time.monotonic() - self._son_tiklama_ts

    def basla(self) -> bool:
        if self._calisiyor:
            return True
        try:
            from pynput import mouse
        except ImportError:
            logger.error("[OTURUM] pynput yüklü değil: pip install pynput")
            return False
        self._calisiyor = True
        with self._lock:
            self._son_tiklama_ts = time.monotonic()
        try:
            self._listener = mouse.Listener(on_click=self._on_click)
            self._listener.daemon = True
            self._listener.start()
        except Exception as e:
            logger.error(f"[OTURUM] Mouse listener hatası: {e}")
            self._calisiyor = False
            return False
        self._worker = threading.Thread(target=self._dongu, daemon=True)
        self._worker.start()
        logger.info(f"[OTURUM] ✓ Canlı tutma başladı (eşik {IDLE_ESIK_SN}s)")
        return True

    def dur(self):
        if not self._calisiyor:
            return
        self._calisiyor = False
        try:
            if self._listener:
                self._listener.stop()
        except Exception:
            pass
        self._listener = None
        logger.info("[OTURUM] Canlı tutma durduruldu")


_servis: Optional[MedulaOturumCanli] = None


def get_servis() -> MedulaOturumCanli:
    global _servis
    if _servis is None:
        _servis = MedulaOturumCanli()
    return _servis


# =====================================================================
# Arka plan (foreground'a almadan) keepalive — ana_menu checkbox için
# =====================================================================

def arkaplan_yenile() -> bool:
    """Medula 'Giriş' butonuna sessizce tıklayarak oturumu canlı tutar.

    Akış:
      1. Medula HWND bul (strict=True, Botanik EOS fallback YOK)
      2. pywinauto UIA ile 'Giriş' butonunu bul → invoke()

    Foreground'a alınmaz, kullanıcı kesintiye uğramaz.

    Returns:
        True  : Giriş butonuna başarıyla tıklandı
        False : Medula penceresi yok ya da Giriş butonu bulunamadı
    """
    try:
        from pencere_yerlesim import _medula_hwnd_bul
        medula_hwnd = _medula_hwnd_bul(strict=True)
    except Exception:
        medula_hwnd = None
    if not medula_hwnd:
        logger.debug(
            "[OTURUM-BG] Medula penceresi bulunamadı — atlanıyor "
            "(Botanik EOS'a tıklanmaz)"
        )
        return False

    try:
        from pywinauto import Application
    except Exception as e:
        logger.error(f"[OTURUM-BG] pywinauto yok: {e}")
        return False

    try:
        app = Application(backend="uia").connect(handle=medula_hwnd)
        w = app.window(handle=medula_hwnd)
    except Exception as e:
        logger.debug(f"[OTURUM-BG] UIA connect hatası: {e}")
        return False

    try:
        for b in w.descendants(control_type="Button"):
            try:
                cap = (b.window_text() or "").strip().replace("&", "")
                if cap == "Giriş" or cap.lower() == "giriş":
                    try:
                        b.invoke()
                        logger.info(
                            f"[OTURUM-BG] ✓ Medula 'Giriş' invoke "
                            f"→ hwnd={medula_hwnd:x}"
                        )
                        return True
                    except Exception as e:
                        logger.debug(f"[OTURUM-BG] invoke hatası: {e}")
                        return False
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[OTURUM-BG] Buton tarama hatası: {e}")
        return False

    logger.warning("[OTURUM-BG] Medula penceresinde 'Giriş' butonu bulunamadı")
    return False
