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

IDLE_ESIK_SN = 119           # 1 dakika 59 saniye (kullanıcı isteği 2026-05-16)
TARAMA_ARALIK_SN = 2
POPUP_BEKLEME_SN = 0.9       # F5 sonrası "sayfayı yeniden yükle?" popup için
POPUP_DOGRULAMA_SN = 0.6     # Enter sonrası popup'ın kapandığını teyit için

# IE WebBrowser ActiveX'in barındırdığı render penceresinin sınıf adı.
# PostMessage F5 buraya gönderilince embedded browser sayfayı yeniler
# (foreground'a alma gerekmez).
_IE_SERVER_CLS = "Internet Explorer_Server"
VK_F5 = 0x74
VK_RETURN = 0x0D



class MedulaOturumCanli:
    def __init__(self):
        self._calisiyor = False
        self._worker: Optional[threading.Thread] = None
        self._listener = None              # mouse listener
        self._kb_listener = None           # keyboard listener
        self._son_tiklama_ts = time.monotonic()
        self._lock = threading.Lock()
        self._son_yenileme_ts = 0.0
        self._son_yontem = ""              # "postmessage" / "foreground" / ""

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

    def _on_key(self, key):
        """Klavye etkinliği: Medula foreground iken keypress idle sayacı resetler.
        Kullanıcı Medula'da form doldururken (fareye dokunmadan) yanlışlıkla
        F5'in patlamasını ve form verisinin uçmasını engeller.
        """
        if not self._calisiyor:
            return
        try:
            import win32gui
            fg = win32gui.GetForegroundWindow()
            if not fg:
                return
            medula_hwnd = self._medula_hwnd()
            if not medula_hwnd:
                return
            # Foreground Medula'nın kendisi ya da Medula'nın bir alt-penceresi mi?
            if fg == medula_hwnd or win32gui.IsChild(medula_hwnd, fg):
                with self._lock:
                    self._son_tiklama_ts = time.monotonic()
        except Exception as e:
            logger.debug(f"_on_key hata: {e}")

    # ---------------------------------------------------------------- refresh

    def _medula_hwnd(self):
        """MEDULA ana HWND'sini bul — strict (Botanik EOS fallback YOK)."""
        try:
            from pencere_yerlesim import _medula_hwnd_bul
            return _medula_hwnd_bul(strict=True)
        except Exception:
            return None

    def _ie_server_child_bul(self, hwnd: int) -> Optional[int]:
        """Medula ana penceresi içinde gömülü 'Internet Explorer_Server' alt
        HWND'sini rekürsif olarak bul. Bulunamazsa None.
        """
        try:
            import win32gui
        except Exception:
            return None

        bulunan: list[int] = []

        def _walk(parent: int):
            if bulunan:
                return
            try:
                cocuklar: list[int] = []

                def _e(c, _):
                    cocuklar.append(c)
                    return True

                win32gui.EnumChildWindows(parent, _e, None)
            except Exception:
                return
            for c in cocuklar:
                try:
                    cls = win32gui.GetClassName(c) or ""
                except Exception:
                    continue
                if cls == _IE_SERVER_CLS:
                    bulunan.append(c)
                    return
            for c in cocuklar:
                _walk(c)
                if bulunan:
                    return

        try:
            _walk(hwnd)
        except Exception as e:
            logger.debug(f"[OTURUM] IE_Server child arama hatası: {e}")
        return bulunan[0] if bulunan else None

    def _popup_dismiss_enter(self, owner_hwnd: int,
                              beklem_sn: float = POPUP_BEKLEME_SN) -> tuple[bool, bool]:
        """Owner pencereye ait modal popup (#32770) belirirse Enter ile dismiss et.

        Medula'da F5 sonrası IE "sayfayı yeniden gönder?" popup'ı için. Popup
        yoksa sessizce (False, False) döner — F5 doğrudan yenilemiş demektir.

        Returns:
            (popup_belirdi, dismiss_basarili)
            - (False, False): timeout içinde popup belirmedi (sorun yok)
            - (True,  True): popup belirdi ve Enter ile kapatıldı
            - (True,  False): popup belirdi ama kapatılamadı (Tier 2 gerekir)
        """
        try:
            import win32api
            import win32con
            import win32gui
        except Exception:
            return (False, False)

        def _popup_ara() -> int:
            adaylar: list[int] = []

            def _e(h, _):
                try:
                    if not win32gui.IsWindowVisible(h):
                        return True
                    cls = win32gui.GetClassName(h) or ""
                    # IE confirm dialog'u #32770 class'lı bir top-level pencere;
                    # owner'ı Medula ana penceresi olur.
                    if cls != "#32770":
                        return True
                    if win32gui.GetWindow(h, win32con.GW_OWNER) == owner_hwnd:
                        adaylar.append(h)
                except Exception:
                    pass
                return True

            try:
                win32gui.EnumWindows(_e, None)
            except Exception:
                pass
            return adaylar[0] if adaylar else 0

        # 1) Popup'ın belirmesini bekle (kısa polling)
        popup_hwnd = 0
        bitis = time.monotonic() + beklem_sn
        while time.monotonic() < bitis:
            popup_hwnd = _popup_ara()
            if popup_hwnd:
                break
            time.sleep(0.08)

        if not popup_hwnd:
            return (False, False)

        try:
            popup_title = win32gui.GetWindowText(popup_hwnd) or "?"
        except Exception:
            popup_title = "?"
        logger.info(
            f"[OTURUM] Popup tespit edildi (hwnd={popup_hwnd:x}, '{popup_title}') "
            f"→ Enter gönderiliyor"
        )

        # 2) Popup'a Enter gönder — default buton (Yeniden Dene / Tamam) tetiklenir
        try:
            scan = win32api.MapVirtualKey(VK_RETURN, 0)
            lp_down = 1 | (scan << 16)
            lp_up = 1 | (scan << 16) | (1 << 30) | (1 << 31)
            win32gui.PostMessage(popup_hwnd, win32con.WM_KEYDOWN, VK_RETURN, lp_down)
            time.sleep(0.03)
            win32gui.PostMessage(popup_hwnd, win32con.WM_KEYUP, VK_RETURN, lp_up)
        except Exception as e:
            logger.warning(f"[OTURUM] Popup Enter PostMessage hatası: {e}")
            return (True, False)

        # 3) Popup'ın kapandığını doğrula
        dogrulama_bitis = time.monotonic() + POPUP_DOGRULAMA_SN
        while time.monotonic() < dogrulama_bitis:
            try:
                if not win32gui.IsWindow(popup_hwnd) or not win32gui.IsWindowVisible(popup_hwnd):
                    logger.info("[OTURUM] ✓ Popup Enter ile kapatıldı")
                    return (True, True)
            except Exception:
                return (True, True)
            time.sleep(0.05)

        logger.warning(
            f"[OTURUM] Popup hâlâ açık (hwnd={popup_hwnd:x}) — foreground fallback gerekecek"
        )
        return (True, False)

    def _f5_postmessage_gonder(self, hwnd: int) -> bool:
        """PostMessage ile embedded IE_Server alt-penceresine F5 gönder ve
        beliren "sayfayı yeniden gönder?" popup'ını Enter ile kapat.

        AVANTAJ: Medula foreground'a alınmaz, kullanıcının başka uygulamadaki
        işi bölünmez; Windows'un SetForegroundWindow kısıtlamalarına takılmaz.

        CLAUDE.md §1 uyumlu: salt sayfa yenileme, veri değiştirmez.
        CLAUDE.md §3 uyumlu: koordinat tıklaması yok, sadece klavye mesajı.

        Returns:
            True  : F5 gönderildi + (varsa) popup Enter ile kapatıldı
            False : IE_Server bulunamadı, F5 gönderilemedi VEYA popup
                    belirdi ama PostMessage Enter ile kapatılamadı
                    (her durumda çağıran Tier 2 fallback'e düşmeli)
        """
        try:
            import win32api
            import win32con
            import win32gui
        except Exception as e:
            logger.error(f"[OTURUM] win32 modülleri yok: {e}")
            return False

        ie_hwnd = self._ie_server_child_bul(hwnd)
        if not ie_hwnd:
            logger.debug(
                f"[OTURUM] IE_Server alt-penceresi bulunamadı "
                f"(parent hwnd={hwnd:x}) — fallback'e düşülecek"
            )
            return False

        try:
            # lParam bit dizilimi (WM_KEYDOWN/WM_KEYUP):
            #   0-15  : repeat count (1)
            #   16-23 : scan code
            #   24    : extended key (0 — F5 extended değil)
            #   25-28 : reserved (0)
            #   29    : context (alt) — 0
            #   30    : previous key state — 0 (down) / 1 (up)
            #   31    : transition state — 0 (down) / 1 (up)
            scan = win32api.MapVirtualKey(VK_F5, 0)  # MAPVK_VK_TO_VSC
            lparam_down = 1 | (scan << 16)
            lparam_up = 1 | (scan << 16) | (1 << 30) | (1 << 31)
            win32gui.PostMessage(ie_hwnd, win32con.WM_KEYDOWN, VK_F5, lparam_down)
            time.sleep(0.03)
            win32gui.PostMessage(ie_hwnd, win32con.WM_KEYUP, VK_F5, lparam_up)
            logger.info(
                f"[OTURUM] ✓ PostMessage F5 → IE_Server (hwnd={ie_hwnd:x})"
            )
        except Exception as e:
            logger.warning(f"[OTURUM] PostMessage F5 hatası: {e}")
            return False

        # F5 sonrası "sayfayı yeniden gönder?" popup'ını Enter ile dismiss et.
        # Popup belirip kapatılamazsa Tier 2'ye düşmesi için False döndür —
        # aksi halde sayfa hiç yenilenmez, oturum düşer.
        popup_belirdi, dismiss_ok = self._popup_dismiss_enter(hwnd)
        if popup_belirdi and not dismiss_ok:
            return False
        return True

    def _f5_ve_enter_gonder(self, hwnd) -> bool:
        """Medula penceresine F5 + (popup için) Enter gönder.

        MEDULA aktif (foreground) ya da arka planda olabilir. Kısa süreliğine
        AttachThreadInput trick'i ile foreground'a alınır, pyautogui ile
        F5 + Enter gönderilir, ardından önceki foreground pencere geri yüklenir.

        SALT YENİLEME — veri değiştirmez (sayfa reload). CLAUDE.md §1 uyumlu.
        pyautogui sadece klavye için kullanılır (koordinat tıklama YOK).
        """
        try:
            import ctypes
            import win32con
            import win32gui
            import win32process
            import pyautogui
        except Exception as e:
            logger.error(f"[OTURUM] F5 modülleri yüklenemedi: {e}")
            return False

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        def _foreground_yap(target_hwnd: int) -> bool:
            if not target_hwnd or not win32gui.IsWindow(target_hwnd):
                return False
            try:
                if win32gui.IsIconic(target_hwnd):
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                cur_thr = kernel32.GetCurrentThreadId()
                tgt_thr, _ = win32process.GetWindowThreadProcessId(target_hwnd)
                attached = False
                if cur_thr != tgt_thr:
                    attached = bool(user32.AttachThreadInput(cur_thr, tgt_thr, True))
                try:
                    win32gui.SetForegroundWindow(target_hwnd)
                finally:
                    if attached:
                        user32.AttachThreadInput(cur_thr, tgt_thr, False)
                return True
            except Exception as e:
                logger.debug(f"[OTURUM] Foreground yapma hatası: {e}")
                return False

        # 1) Önceki foreground'u kaydet ki sonradan geri verelim
        try:
            onceki_fg = win32gui.GetForegroundWindow()
        except Exception:
            onceki_fg = 0

        # 2) Medula'yı foreground'a al
        if not _foreground_yap(hwnd):
            logger.warning("[OTURUM] Medula foreground'a alınamadı — atlanıyor")
            return False
        time.sleep(0.2)

        # 3) F5 gönder, popup için bekle, Enter ile onayla
        basarili = False
        try:
            pyautogui.press('f5')
            time.sleep(POPUP_BEKLEME_SN)
            pyautogui.press('enter')
            logger.info("[OTURUM] ✓ Medula F5 + Enter gönderildi")
            basarili = True
        except Exception as e:
            logger.error(f"[OTURUM] F5/Enter gönderme hatası: {e}")

        # 4) Önceki foreground'u geri yükle (kullanıcının işi bölünmesin)
        if onceki_fg and onceki_fg != hwnd:
            _foreground_yap(onceki_fg)

        return basarili

    def _oturumu_yenile(self):
        """MEDULA penceresine F5 göndererek oturumu canlı tutar.

        İki kademeli akış:
          Tier 1 — PostMessage: foreground'a almadan IE_Server alt-penceresine
                   doğrudan WM_KEYDOWN(VK_F5) gönder. Kullanıcıyı bölmez.
          Tier 2 — Foreground+pyautogui: Tier 1 başarısız olursa Medula kısa
                   süreliğine öne alınır, pyautogui ile F5+Enter gönderilir
                   (popup ihtimaline karşı Enter), sonra önceki pencere geri
                   yüklenir.

        Botanik EOS fallback kapalı olduğu için Medula penceresi yoksa
        hiçbir şey yapılmaz (Botanik EOS'a yanlışlıkla F5 gönderme bug'ını
        engeller).
        """
        logger.info(
            f"[OTURUM] {IDLE_ESIK_SN}s idle — Medula sessiz F5 deneniyor"
        )
        try:
            hwnd = self._medula_hwnd()
            if not hwnd:
                logger.warning(
                    "[OTURUM] Medula penceresi bulunamadı — atlanıyor "
                    "(Botanik EOS'a tıklanmaz)"
                )
                return

            # Tier 1: foreground'a almadan PostMessage F5
            if self._f5_postmessage_gonder(hwnd):
                self._son_yenileme_ts = time.monotonic()
                self._son_yontem = "postmessage"
                return

            # Tier 2: PostMessage çalışmadı → mevcut foreground+pyautogui
            logger.warning(
                "[OTURUM] PostMessage F5 başarısız — foreground fallback'e geçiliyor"
            )
            if self._f5_ve_enter_gonder(hwnd):
                self._son_yenileme_ts = time.monotonic()
                self._son_yontem = "foreground"
            else:
                self._son_yontem = ""
                logger.error("[OTURUM] Hem PostMessage hem foreground F5 başarısız")
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
            from pynput import keyboard, mouse
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
        # Klavye listener (opsiyonel — başarısız olsa bile sistemi çalıştır)
        try:
            self._kb_listener = keyboard.Listener(on_press=self._on_key)
            self._kb_listener.daemon = True
            self._kb_listener.start()
        except Exception as e:
            logger.warning(f"[OTURUM] Klavye listener kurulamadı (devam): {e}")
            self._kb_listener = None
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
        try:
            if self._kb_listener:
                self._kb_listener.stop()
        except Exception:
            pass
        self._kb_listener = None
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
    """MEDULA penceresine F5 göndererek oturumu canlı tutar (manuel tetik).

    İki kademeli akış (servis döngüsündeki mantığın aynısı):
      Tier 1 — PostMessage F5 (foreground'a almaz, kullanıcıyı bölmez)
      Tier 2 — Foreground + pyautogui F5+Enter (fallback)

    Returns:
        True  : F5 başarıyla gönderildi (Tier 1 ya da Tier 2 başardı)
        False : Medula penceresi yok ya da her iki tier de başarısız
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

    servis = get_servis()
    if servis._f5_postmessage_gonder(medula_hwnd):
        return True
    logger.warning(
        "[OTURUM-BG] PostMessage F5 başarısız — foreground fallback'e geçiliyor"
    )
    return servis._f5_ve_enter_gonder(medula_hwnd)
