# -*- coding: utf-8 -*-
"""
Medula Oturum Canlı Tutma Servisi

Arka planda çalışır, Medula oturumunu düşürmez.
Her 20 saniyede sol menüdeki bir elemente tıklayarak oturumu yeniler.
Oturum düşmüşse Giriş butonuna basarak yeniden bağlanır.

Kullanım:
    python medula_keepalive.py          # Başlat
    python medula_keepalive.py stop     # Durdur (PID dosyası ile)
"""

import time
import sys
import os
import logging

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [KEEPALIVE] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keepalive.pid")
KEEPALIVE_ARALIK = 20  # saniye


def medula_penceresi_bul():
    """MEDULA penceresini bul ve pywinauto wrapper döndür"""
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for window in desktop.windows():
            try:
                title = window.window_text()
                if "MEDULA" in title:
                    return desktop.window(handle=window.handle)
            except:
                continue
    except Exception as e:
        log.error(f"Pencere arama hatası: {e}")
    return None


def oturum_aktif_mi(main_window):
    """Sol menü görünüyor mu?"""
    try:
        for elem in main_window.descendants():
            try:
                if elem.element_info.automation_id == "form1:menuHtmlCommandExButton31":
                    return True
            except:
                pass
    except:
        pass
    return False


def oturumu_yenile(main_window):
    """Giriş butonuna basarak oturumu yenile"""
    try:
        for elem in main_window.descendants(control_type="Button"):
            try:
                if elem.element_info.automation_id == "btnMedulayaGirisYap":
                    elem.click_input()
                    log.info("Giriş butonuna tıklandı")
                    return True
            except:
                pass
    except:
        pass
    return False


def keepalive_tiklama(main_window):
    """WM_MOUSEMOVE gönder (aktivite simüle et, sayfa değişmez)"""
    try:
        import win32gui
        for window in main_window.descendants(control_type="Pane"):
            try:
                hwnd = window.handle
                win32gui.PostMessage(hwnd, 0x0200, 0, 0)
                break
            except:
                pass
    except:
        pass


def ana_dongu():
    """Ana keepalive döngüsü"""
    # PID kaydet
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    log.info(f"Keepalive başlatıldı (PID: {os.getpid()}, aralık: {KEEPALIVE_ARALIK}s)")

    hata_sayaci = 0
    while True:
        try:
            time.sleep(KEEPALIVE_ARALIK)

            # Medula penceresini bul
            main_window = medula_penceresi_bul()
            if not main_window:
                hata_sayaci += 1
                if hata_sayaci % 10 == 0:
                    log.warning("Medula penceresi bulunamadı")
                continue

            hata_sayaci = 0

            # Oturum aktif mi?
            if oturum_aktif_mi(main_window):
                keepalive_tiklama(main_window)
                log.debug("Keepalive OK")
            else:
                log.warning("Oturum düşmüş, yenileniyor...")
                for deneme in range(3):
                    oturumu_yenile(main_window)
                    time.sleep(5)
                    if oturum_aktif_mi(main_window):
                        log.info("Oturum yenilendi!")
                        break
                else:
                    log.error("Oturum yenilenemedi!")

        except KeyboardInterrupt:
            log.info("Keepalive durduruldu (Ctrl+C)")
            break
        except Exception as e:
            log.error(f"Keepalive hatası: {e}")
            time.sleep(5)

    # PID dosyasını temizle
    try:
        os.remove(PID_FILE)
    except:
        pass


def durdur():
    """Çalışan keepalive'ı durdur"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            log.info(f"Keepalive durduruldu (PID: {pid})")
        except ProcessLookupError:
            log.info("Keepalive zaten çalışmıyor")
        os.remove(PID_FILE)
    else:
        log.info("Keepalive PID dosyası bulunamadı")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        durdur()
    else:
        ana_dongu()
