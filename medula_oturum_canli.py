"""
MEDULA Oturum Canlı Tutucu
--------------------------
MEDULA penceresine yapılan tıklamaları dinler.
Belirli süre (varsayılan 110 sn = 1 dk 50 sn) boyunca MEDULA içinde
tıklama olmazsa:
  1) MEDULA'ya F5 gönder (sayfa yenile)
  2) Açılan popup'taki "Tamam" / "OK" / "Evet" butonuna bas
  3) 300 ms sonra Enter gönder
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

IDLE_ESIK_SN = 110           # 1 dakika 50 saniye
TARAMA_ARALIK_SN = 2
POPUP_ENTER_GECIKME_SN = 0.3
POPUP_BEKLEME_SN = 3.0       # F5 sonrası popup kaç saniye beklensin


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
            hwnd = _medula_hwnd_bul()
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

    def _popup_tamam_tikla(self) -> bool:
        """F5 sonrası açılan popup'taki 'Yeniden Dene' / 'Tamam' butonuna bas.

        Native #32770 Windows dialog'u BM_CLICK'i yoksayar — gerçek mouse
        click simülasyonu (click_input) gerekir.

        SALT NAVİGASYON — veri değiştirmez.
        """
        # Yeniden Dene öncelikli (IE "retry" popup'ı)
        hedef_captions = ("Yeniden Dene", "Tamam", "OK", "Evet", "Yes")

        # 1) win32gui ile popup HWND'sini hızlıca bul
        try:
            import win32gui
        except Exception:
            win32gui = None

        popup_hwnd = None
        if win32gui is not None:
            hedef_dialog = [None]

            def _enum_top(top_hwnd, _):
                try:
                    if not win32gui.IsWindowVisible(top_hwnd):
                        return True
                    title = (win32gui.GetWindowText(top_hwnd) or "").strip()
                    if len(title) > 100:
                        return True
                    # #32770 (standart dialog) veya sahte dialog adayları
                    try:
                        cls = win32gui.GetClassName(top_hwnd) or ""
                    except Exception:
                        cls = ""
                    if cls != "#32770":
                        return True
                    # Çocuk butonlarını kontrol et — hedef caption var mı?
                    bulundu = [False]

                    def _enum_child(c_hwnd, __):
                        try:
                            ccls = win32gui.GetClassName(c_hwnd) or ""
                            if ccls != "Button":
                                return True
                            cap = (win32gui.GetWindowText(c_hwnd) or "").strip()
                            cap_tmz = cap.replace("&", "")
                            if cap_tmz in hedef_captions:
                                bulundu[0] = True
                                return False
                        except Exception:
                            pass
                        return True

                    try:
                        win32gui.EnumChildWindows(top_hwnd, _enum_child, None)
                    except Exception:
                        pass
                    if bulundu[0]:
                        hedef_dialog[0] = (top_hwnd, title)
                        return False
                except Exception:
                    pass
                return True

            try:
                win32gui.EnumWindows(_enum_top, None)
            except Exception:
                pass
            if hedef_dialog[0]:
                popup_hwnd, popup_title = hedef_dialog[0]
                logger.debug(f"[OTURUM] Popup HWND bulundu: {popup_hwnd:x} '{popup_title}'")

        # 2) Popup yoksa None dön
        if popup_hwnd is None:
            return False

        # 3) ÖNCE: WM_COMMAND IDRETRY (4) — #32770 dialog'a native komut
        # IDRETRY=4, IDOK=1, IDCANCEL=2, IDYES=6
        # Popup'ta Yeniden Dene butonu varsa IDRETRY yeterli olur
        try:
            import win32con
            # IDRETRY önce dene (Yeniden Dene için)
            for idx in (4, 1, 6):  # IDRETRY, IDOK, IDYES
                try:
                    win32gui.PostMessage(
                        popup_hwnd, win32con.WM_COMMAND, idx, 0,
                    )
                    logger.info(
                        f"[OTURUM] Popup '{popup_title}' → WM_COMMAND "
                        f"id={idx} gönderildi"
                    )
                    # Popup'un kapanmasını bekle (max 1 sn)
                    import time as _t
                    for _ in range(10):
                        _t.sleep(0.1)
                        if not win32gui.IsWindow(popup_hwnd):
                            return True
                        if not win32gui.IsWindowVisible(popup_hwnd):
                            return True
                    # Hala duruyorsa bir sonraki id'yi dene
                except Exception as e:
                    logger.debug(f"WM_COMMAND {idx} hatası: {e}")
        except Exception as e:
            logger.debug(f"WM_COMMAND yolu hatası: {e}")

        # 4) FALLBACK: pywinauto UIA ile click_input (gerçek mouse)
        try:
            from pywinauto import Application
            app = Application(backend="uia").connect(handle=popup_hwnd)
            w = app.window(handle=popup_hwnd)
            hedef_btn = None
            secilen_cap = None
            for hc in hedef_captions:
                if hedef_btn is not None:
                    break
                try:
                    for b in w.descendants(control_type="Button"):
                        try:
                            cap = (b.window_text() or "").strip().replace("&", "")
                            if cap == hc:
                                hedef_btn = b
                                secilen_cap = cap
                                break
                        except Exception:
                            continue
                except Exception:
                    continue
            if hedef_btn is None:
                logger.debug("[OTURUM] Popup içinde hedef buton bulunamadı")
                return False
            try:
                hedef_btn.click_input()
                logger.info(
                    f"[OTURUM] Popup '{popup_title}' → '{secilen_cap}' (click_input)"
                )
                return True
            except Exception as e:
                logger.debug(f"click_input hatası: {e}")
                try:
                    hedef_btn.invoke()
                    logger.info(
                        f"[OTURUM] Popup '{popup_title}' → '{secilen_cap}' (invoke)"
                    )
                    return True
                except Exception as e2:
                    logger.debug(f"invoke hatası: {e2}")
        except Exception as e:
            logger.debug(f"UIA connect hatası: {e}")
        return False

    def _medula_hwnd(self):
        """MEDULA ana HWND'sini bul (is_visible takıntısı olmadan)."""
        try:
            from pencere_yerlesim import _medula_hwnd_bul
            return _medula_hwnd_bul()
        except Exception:
            return None

    def _ie_server_hwnd(self, parent_hwnd):
        """MEDULA içindeki Internet Explorer_Server child HWND'sini bul."""
        try:
            import win32gui
            bulunan = [None]

            def _enum(h, _):
                try:
                    cls = win32gui.GetClassName(h) or ""
                    if "Internet Explorer_Server" in cls:
                        bulunan[0] = h
                        return False
                except Exception:
                    pass
                return True

            try:
                win32gui.EnumChildWindows(parent_hwnd, _enum, None)
            except Exception:
                pass
            return bulunan[0]
        except Exception as e:
            logger.debug(f"IE server bul hatası: {e}")
            return None

    def _medulayi_one_getir(self, hwnd) -> bool:
        """SetForegroundWindow Windows foreground lock'u aşsın diye
        önce ALT-down/ALT-up göndererek 'input state'i sıfırla."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # ALT basıp bırak (foreground lock geçici olarak açılır)
            user32.keybd_event(0x12, 0, 0, 0)       # ALT down
            user32.keybd_event(0x12, 0, 0x0002, 0)  # ALT up
            time.sleep(0.02)
            try:
                import win32gui
                import win32con
                # Maximize/Restore isimlemeyelim — sadece öne getir
                try:
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                except Exception:
                    pass
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                return True
            except Exception as e:
                logger.debug(f"SetForegroundWindow hatası: {e}")
                return False
        except Exception as e:
            logger.debug(f"_medulayi_one_getir hatası: {e}")
            return False

    def _tus_gonder_vk(self, vk: int, hwnd: int = None):
        """Tuş gönder. Sıra:
           1. pyautogui (aktif pencereye)
           2. PostMessage (arkaplandayken)
        """
        basarili = False
        # 1. pyautogui (aktif pencereye gider)
        try:
            import pyautogui
            isim = {0x74: "f5", 0x0D: "enter"}.get(vk, str(vk))
            pyautogui.press(isim)
            basarili = True
            logger.debug(f"[OTURUM] Tuş pyautogui ile gönderildi: {isim}")
        except Exception as e:
            logger.debug(f"pyautogui.press hatası: {e}")

        # 2. PostMessage — IE_Server varsa oraya, yoksa ana HWND'ye
        if hwnd:
            try:
                import win32api
                import win32con
                hedef = self._ie_server_hwnd(hwnd) or hwnd
                win32api.PostMessage(hedef, win32con.WM_KEYDOWN, vk, 0)
                time.sleep(0.03)
                win32api.PostMessage(hedef, win32con.WM_KEYUP, vk, 0)
                basarili = True
                logger.debug(
                    f"[OTURUM] Tuş PostMessage ile gönderildi: vk={vk:x} hwnd={hedef}"
                )
            except Exception as e:
                logger.debug(f"PostMessage hatası: {e}")
        return basarili

    def _oturumu_yenile(self):
        """F5 → popup 'Yeniden Dene' butonuna bas.

        Enter işe yaramadığı için kaldırıldı. Popup 'Yeniden Dene' / 'Tamam'
        butonu native Win32 Button — BM_CLICK ile tıklanır.
        """
        logger.info(f"[OTURUM] {IDLE_ESIK_SN}s idle — oturum yenileniyor")
        try:
            hwnd = self._medula_hwnd()
            if not hwnd:
                logger.warning("[OTURUM] MEDULA HWND bulunamadı")
                return

            # 1) MEDULA'yı öne getir
            one_alindi = self._medulayi_one_getir(hwnd)
            time.sleep(0.15 if one_alindi else 0.05)

            # 2) F5 gönder (çifte yol: pyautogui + PostMessage)
            logger.info("[OTURUM] → F5 gönderiliyor")
            self._tus_gonder_vk(0x74, hwnd)  # VK_F5

            # 3) Popup görünene kadar inatçı tara — her 150 ms,
            #    toplam POPUP_BEKLEME_SN süresince
            tiklandi = False
            son = time.monotonic() + POPUP_BEKLEME_SN
            while time.monotonic() < son:
                time.sleep(0.15)
                if self._popup_tamam_tikla():
                    tiklandi = True
                    break

            if tiklandi:
                logger.info("[OTURUM] ✓ F5 + Yeniden Dene tamamlandı")
            else:
                logger.debug("[OTURUM] Popup bulunamadı — sadece F5 yeterli")
            self._son_yenileme_ts = time.monotonic()
        except Exception as e:
            logger.error(f"[OTURUM] Yenileme hatası: {e}", exc_info=True)

    # ---------------------------------------------------------------- loop

    def _dongu(self):
        while self._calisiyor:
            try:
                with self._lock:
                    gecen = time.monotonic() - self._son_tiklama_ts
                if gecen >= IDLE_ESIK_SN:
                    self._oturumu_yenile()
                    with self._lock:
                        self._son_tiklama_ts = time.monotonic()
            except Exception as e:
                logger.error(f"[OTURUM] Döngü hatası: {e}")
            time.sleep(TARAMA_ARALIK_SN)

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
