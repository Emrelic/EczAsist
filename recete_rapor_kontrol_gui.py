# -*- coding: utf-8 -*-
"""
Reçete / Rapor Kontrol Modülü GUI

Ana menüden açılan, grup bazlı reçete kontrol ekranı.
Her grup için kaldığı yerden devam edebilir.
Medula bağlantısı kurarak reçeteleri kontrol eder.

MEDULA ELEMENT ID'LERİ (Öğrenildi 2026-03-24):
================================================
Giriş Penceresi (BotanikEOS 2.1.223.0 (T)):
  - Kullanıcı combo: auto_id="cmbKullanicilar"
  - Şifre: auto_id="txtSifre"
  - Giriş butonu: auto_id="btnGirisYap"

Sol Menü:
  - e-Reçete Sorgu: auto_id="form1:menuHtmlCommandExButton11"
  - Reçete Giriş: auto_id="form1:menuHtmlCommandExButton21"
  - Reçete Listesi: auto_id="form1:menuHtmlCommandExButton31"
  - Reçete Listesi (Günlük): auto_id="form1:menuHtmlCommandExButton41"
  - Reçete Sorgu: auto_id="form1:menuHtmlCommandExButton51"
  - İade Reçete: auto_id="form1:menuHtmlCommandExButton61"
  - İlaç Bilgisi: auto_id="form1:menuHtmlCommandExButton71"
  - Fatura Sonlandırma: auto_id="form1:menuHtmlCommandExButton121"

Reçete Listesi Sayfası:
  - Fatura Türü dropdown: auto_id="form1:menu1"
  - Dönem dropdown: auto_id="form1:menu2"
  - Sorgula butonu: auto_id="form1:buttonSonlandirilmamisReceteler"
  - Grup sekmeleri (DataItem, title ile erişilir):
      "A", "B", "C Sıralı", "C Kan", "GKKKOY", "Yurtdışı"
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
import os
import subprocess
import time
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# Proje dizini
PROJE_DIZINI = os.path.dirname(os.path.abspath(__file__))
DURUM_DOSYASI = os.path.join(PROJE_DIZINI, "recete_kontrol_durumlari.json")

# Medula exe yolu
MEDULA_EXE = r"C:\BotanikEczane\BotanikMedula.exe"

# Medula giriş bilgileri
MEDULA_KULLANICI = "16-botan "
MEDULA_SIFRE = "152634"

# Grup tanımları - sıralı
# kod: bizim kodumuzu, medula_tab: Medula'daki sekme adı
GRUP_TANIMLARI = [
    {"kod": "C", "ad": "C Grubu", "medula_tab": "C Sıralı", "renk": "#4CAF50", "hover": "#388E3C"},
    {"kod": "A", "ad": "A Grubu", "medula_tab": "A", "renk": "#2196F3", "hover": "#1976D2"},
    {"kod": "B", "ad": "B Grubu", "medula_tab": "B", "renk": "#FF9800", "hover": "#F57C00"},
    {"kod": "CK", "ad": "C Grubu Kan Ürünü", "medula_tab": "C Kan", "renk": "#F44336", "hover": "#D32F2F"},
    {"kod": "GK", "ad": "Geçici Koruma", "medula_tab": "GKKKOY", "renk": "#9C27B0", "hover": "#7B1FA2"},
]

# Medula AutomationID sabitleri
MEDULA_IDS = {
    # Giriş penceresi
    "giris_kullanici_combo": "cmbKullanicilar",
    "giris_sifre": "txtSifre",
    "giris_butonu": "btnGirisYap",
    # Sol menü
    "menu_recete_listesi": "form1:menuHtmlCommandExButton31",
    "menu_erecete_sorgu": "form1:menuHtmlCommandExButton11",
    "menu_recete_giris": "form1:menuHtmlCommandExButton21",
    "menu_recete_sorgu": "form1:menuHtmlCommandExButton51",
    "menu_ilac_bilgisi": "form1:menuHtmlCommandExButton71",
    # Reçete Listesi sayfası
    "fatura_turu_combo": "form1:menu1",
    "donem_combo": "form1:menu2",
    "sorgula_butonu": "form1:buttonSonlandirilmamisReceteler",
}


class MedulaBaglanti:
    """
    Medula (BotanikEOS) pencere bağlantısı ve kontrolü.

    Bağlantı akışı:
    1. MEDULA penceresi açık mı? → Direkt bağlan
    2. Giriş penceresi açık mı? → Kullanıcı seç, şifre gir, giriş butonuna birkaç kez bas
    3. Hiçbiri yok? → Exe'den başlat → Giriş yap
    4. Giriş başarısız? → taskkill ile kapat → Exe'den tekrar başlat → Giriş yap
    """

    MAX_GIRIS_DENEME = 4       # Giriş butonuna kaç kez basılacak
    GIRIS_BEKLEME = 3          # Her giriş denemesi arası bekleme (sn)
    EXE_ACILMA_BEKLEME = 12    # Exe başlatıldıktan sonra bekleme (sn)
    KEEPALIVE_ARALIK = 30      # Oturum canlı tutma aralığı (saniye)

    def __init__(self, log_callback=None):
        self.main_window = None
        self.medula_hwnd = None
        self.bagli = False
        self.log = log_callback or (lambda msg, tag="info": logger.info(msg))
        self._keepalive_thread = None
        self._keepalive_aktif = False

    # === PENCERE TARAMA ===

    def _pencereleri_tara(self):
        """
        Tüm pencereleri tara ve Medula ile ilgili olanları döndür.
        Returns:
            dict: {"medula": [(hwnd, title), ...], "giris": [(hwnd, title), ...]}
        """
        import win32gui
        medula = []
        giris = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if "MEDULA" in t:
                    medula.append((hwnd, t))
                elif "BotanikEOS" in t and "(T)" in t:
                    giris.append((hwnd, t))

        win32gui.EnumWindows(callback, None)
        return {"medula": medula, "giris": giris}

    def medula_acik_mi(self):
        """Medula durumunu kontrol et. Eski arayüz uyumluluğu için."""
        try:
            sonuc = self._pencereleri_tara()
            if sonuc["medula"]:
                return "bagli", sonuc["medula"]
            elif sonuc["giris"]:
                return "giris_bekliyor", sonuc["giris"]
            else:
                return "kapali", []
        except Exception as e:
            logger.error(f"Medula kontrol hatası: {e}")
            return "hata", []

    # === BAĞLANTI ===

    def medula_baglan(self):
        """Açık olan MEDULA penceresine pywinauto ile bağlan ve keepalive başlat"""
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")

            for window in desktop.windows():
                try:
                    title = window.window_text()
                    if "MEDULA" in title:
                        self.main_window = desktop.window(handle=window.handle)
                        self.medula_hwnd = window.handle
                        self.bagli = True
                        self.log(f"Medula'ya bağlandı: {title}", "success")
                        # Oturum canlı tutma başlat
                        self.keepalive_baslat()
                        return True
                except Exception:
                    continue

            self.log("MEDULA penceresi bulunamadı", "error")
            return False
        except Exception as e:
            self.log(f"Bağlantı hatası: {e}", "error")
            return False

    # === ANA AKIŞ ===

    def medula_ac_ve_baglan(self):
        """
        Medula'yı aç ve bağlan. Tam akış:
        1. MEDULA penceresi açık mı? → Bağlan
        2. Giriş penceresi açık mı? → Giriş yap (birkaç deneme)
        3. Hiçbiri yok? → Exe başlat → Giriş yap
        4. Hepsi başarısız? → taskkill → Exe başlat → Giriş yap (son şans)
        """
        # 1. MEDULA penceresi zaten açık mı?
        sonuc = self._pencereleri_tara()
        if sonuc["medula"]:
            self.log("Medula zaten açık, bağlanılıyor...", "info")
            return self.medula_baglan()

        # 2. Giriş penceresi açık mı?
        if sonuc["giris"]:
            self.log("Giriş penceresi bulundu, giriş yapılıyor...", "info")
            basarili = self._giris_yap()
            if basarili:
                return True
            # Giriş başarısız - taskkill ve yeniden dene
            self.log("Giriş başarısız, Medula yeniden başlatılıyor...", "warning")
            self._medula_kapat()
            time.sleep(2)
            return self._exe_baslat_ve_giris_yap()

        # 3. Hiçbiri yok - exe'den başlat
        return self._exe_baslat_ve_giris_yap()

    # === EXE BAŞLATMA ===

    def _exe_baslat_ve_giris_yap(self):
        """Exe'yi başlat, giriş yap. Başarısız olursa taskkill edip tekrar dene."""
        if not os.path.exists(MEDULA_EXE):
            self.log(f"Medula exe bulunamadı: {MEDULA_EXE}", "error")
            return False

        self.log("Medula başlatılıyor...", "info")
        subprocess.Popen([MEDULA_EXE])
        time.sleep(self.EXE_ACILMA_BEKLEME)

        basarili = self._giris_yap()
        if basarili:
            return True

        # Son şans: taskkill ve tekrar dene
        self.log("Giriş başarısız, taskkill ile kapatılıp tekrar deneniyor...", "warning")
        self._medula_kapat()
        time.sleep(3)

        self.log("Medula tekrar başlatılıyor...", "info")
        subprocess.Popen([MEDULA_EXE])
        time.sleep(self.EXE_ACILMA_BEKLEME)

        return self._giris_yap()

    # === GİRİŞ ===

    def _giris_yap(self):
        """
        Giriş penceresini bul, kullanıcı seç, şifre gir, giriş butonuna
        birkaç kez 2sn aralıkla bas. Her denemeden sonra MEDULA penceresi
        açıldı mı kontrol et.
        """
        try:
            from pywinauto import Desktop
            import pyautogui

            desktop = Desktop(backend="uia")
            time.sleep(2)

            # Giriş penceresini bul
            giris_window = self._giris_penceresi_bul(desktop)
            if not giris_window:
                return False

            giris_window.set_focus()
            time.sleep(0.5)

            # 1. Kullanıcı seç
            if not self._kullanici_sec(giris_window):
                return False

            # 2. Şifre gir
            if not self._sifre_gir(giris_window):
                return False

            # 3. Giriş butonuna birkaç kez bas, her seferinde kontrol et
            for deneme in range(1, self.MAX_GIRIS_DENEME + 1):
                self.log(f"Giriş deneme {deneme}/{self.MAX_GIRIS_DENEME}...", "info")

                try:
                    giris_btn = giris_window.child_window(auto_id=MEDULA_IDS["giris_butonu"])
                    giris_btn.click_input()
                except Exception as e:
                    self.log(f"Giriş butonu tıklanamadı: {e}", "warning")

                time.sleep(self.GIRIS_BEKLEME)

                # MEDULA penceresi açıldı mı?
                sonuc = self._pencereleri_tara()
                if sonuc["medula"]:
                    self.log("Medula açıldı!", "success")
                    return self.medula_baglan()

            self.log(f"{self.MAX_GIRIS_DENEME} deneme sonrası Medula açılamadı", "error")
            return False

        except Exception as e:
            self.log(f"Giriş hatası: {e}", "error")
            return False

    def _giris_penceresi_bul(self, desktop, max_bekleme=15):
        """
        Giriş penceresini bul (BotanikEOS ... (T) ama MEDULA değil).
        max_bekleme saniye boyunca dener.
        """
        for bekle in range(max_bekleme):
            for window in desktop.windows():
                try:
                    title = window.window_text()
                    if "BotanikEOS" in title and "(T)" in title and "MEDULA" not in title:
                        self.log(f"Giriş penceresi: {title}", "info")
                        return desktop.window(handle=window.handle)
                except Exception:
                    continue

            if bekle < max_bekleme - 1:
                time.sleep(1)

        self.log("Giriş penceresi bulunamadı", "error")
        return None

    def _kullanici_sec(self, giris_window):
        """Dropdown'dan botan kullanıcısını seç"""
        try:
            combo = giris_window.child_window(auto_id=MEDULA_IDS["giris_kullanici_combo"])
            combo.click_input()
            time.sleep(0.5)

            items = combo.descendants(control_type="ListItem")
            for item in items:
                try:
                    if "botan" in item.window_text().lower():
                        item.click_input()
                        self.log("Kullanıcı seçildi: botan", "success")
                        time.sleep(0.3)
                        return True
                except Exception:
                    continue

            self.log("'botan' kullanıcısı bulunamadı!", "error")
            return False
        except Exception as e:
            self.log(f"Kullanıcı seçme hatası: {e}", "error")
            return False

    def _sifre_gir(self, giris_window):
        """Şifre alanına şifreyi gir"""
        try:
            import pyautogui
            sifre = giris_window.child_window(auto_id=MEDULA_IDS["giris_sifre"])
            sifre.click_input()
            time.sleep(0.2)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            sifre.type_keys(MEDULA_SIFRE, with_spaces=True)
            self.log("Şifre girildi", "info")
            time.sleep(0.3)
            return True
        except Exception as e:
            self.log(f"Şifre girme hatası: {e}", "error")
            return False

    # === KAPATMA ===

    def _medula_kapat(self):
        """BotanikMedula.exe'yi taskkill ile kapat"""
        try:
            self.keepalive_durdur()

            result = subprocess.run(
                ["taskkill", "/F", "/IM", "BotanikMedula.exe"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.log("BotanikMedula.exe kapatıldı (taskkill)", "info")
            else:
                self.log("BotanikMedula.exe bulunamadı veya kapatılamadı", "warning")

            self.main_window = None
            self.medula_hwnd = None
            self.bagli = False
        except Exception as e:
            self.log(f"Taskkill hatası: {e}", "error")

    # === YARDIMCI ===

    def pencereyi_aktifle(self):
        """Medula penceresini öne getir"""
        try:
            import win32gui, win32con
            if self.medula_hwnd:
                win32gui.ShowWindow(self.medula_hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
                win32gui.SetForegroundWindow(self.medula_hwnd)
                time.sleep(0.3)
                return True
        except Exception as e:
            logger.error(f"Pencere aktifleştirme hatası: {e}")
        return False

    # === OTURUM CANLI TUTMA (KEEPALIVE) ===

    def keepalive_baslat(self):
        """
        Arka planda periyodik olarak Medula web sayfasındaki sol menüde
        e-Reçete Sorgu linkine tıklayarak oturumu canlı tut.
        Bu tıklama web sunucusuna istek göndererek session timeout'u sıfırlar.
        """
        if self._keepalive_aktif:
            return

        self._keepalive_aktif = True

        def keepalive_loop():
            import win32gui, win32con

            while self._keepalive_aktif and self.bagli:
                try:
                    time.sleep(self.KEEPALIVE_ARALIK)
                    if not self._keepalive_aktif or not self.bagli:
                        break

                    if not self.medula_hwnd or not self.main_window:
                        continue

                    # 1. Pencereye Windows mesajı gönder (aktivite simüle et)
                    try:
                        # WM_MOUSEMOVE - pencere içinde mouse hareketi simüle et
                        win32gui.PostMessage(self.medula_hwnd, 0x0200, 0, 0)
                        logger.debug("Keepalive: WM_MOUSEMOVE gönderildi")
                    except:
                        pass

                    # 2. Sol menüdeki bir elemente tıkla (web isteği = oturum yenilenir)
                    try:
                        for elem in self.main_window.descendants():
                            try:
                                aid = elem.element_info.automation_id
                                if aid == MEDULA_IDS["menu_erecete_sorgu"]:
                                    elem.click_input()
                                    logger.debug("Keepalive: e-Reçete Sorgu tıklandı")
                                    break
                            except:
                                pass
                    except:
                        pass

                except Exception as e:
                    logger.debug(f"Keepalive hatası: {e}")

        self._keepalive_thread = threading.Thread(target=keepalive_loop, daemon=True)
        self._keepalive_thread.start()
        self.log("Oturum canlı tutma başlatıldı", "info")

    def keepalive_durdur(self):
        """Keepalive döngüsünü durdur"""
        self._keepalive_aktif = False
        self._keepalive_thread = None

    # === NAVİGASYON FONKSİYONLARI ===

    def _element_bul_ve_tikla(self, auto_id, aciklama=""):
        """AutomationID ile element bul ve tıkla (descendants ile güvenilir arama)"""
        try:
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == auto_id:
                        elem.click_input()
                        if aciklama:
                            self.log(aciklama, "success")
                        return True
                except:
                    pass
            self.log(f"Element bulunamadı: {auto_id}", "error")
            return False
        except Exception as e:
            self.log(f"Element tıklama hatası ({auto_id}): {e}", "error")
            return False

    def recete_listesine_git(self):
        """Sol menüdeki 'Reçete Listesi' butonuna tıkla"""
        if not self.bagli:
            self.log("Medula'ya bağlı değil!", "error")
            return False

        basarili = self._element_bul_ve_tikla(
            MEDULA_IDS["menu_recete_listesi"],
            "Reçete Listesi sayfasına gidildi"
        )
        if basarili:
            time.sleep(2)
        return basarili

    def grup_sekmesine_tikla(self, grup_kodu):
        """
        Reçete Listesi sayfasındaki grup sekmesine tıkla.
        grup_kodu: "C", "A", "B", "CK", "GK"
        """
        if not self.bagli:
            return False

        # Grup kodunu Medula sekme adına çevir
        grup_bilgi = next((g for g in GRUP_TANIMLARI if g["kod"] == grup_kodu), None)
        if not grup_bilgi:
            self.log(f"Bilinmeyen grup: {grup_kodu}", "error")
            return False

        medula_tab = grup_bilgi["medula_tab"]

        try:
            # DataItem olarak bul ve tıkla
            tab_items = self.main_window.descendants(
                title=medula_tab, control_type="DataItem"
            )
            if tab_items:
                tab_items[0].click_input()
                self.log(f"'{medula_tab}' sekmesine tıklandı", "success")
                time.sleep(1)
                return True
            else:
                self.log(f"'{medula_tab}' sekmesi bulunamadı", "error")
                return False
        except Exception as e:
            self.log(f"Sekme tıklama hatası: {e}", "error")
            return False

    def sorgula(self):
        """Sorgula butonuna tıkla"""
        if not self.bagli:
            return False

        basarili = self._element_bul_ve_tikla(
            MEDULA_IDS["sorgula_butonu"],
            "Sorgula butonuna tıklandı"
        )
        if basarili:
            time.sleep(3)
        return basarili

    # === OTURUM KONTROLÜ ===

    def oturum_aktif_mi(self):
        """Sol menü görünüyor mu? (oturum düşmüşse menü kaybolur)"""
        if not self.bagli:
            return False
        try:
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == MEDULA_IDS["menu_recete_listesi"]:
                        return True
                except:
                    pass
            return False
        except:
            return False

    def oturumu_yenile(self):
        """
        Oturum düşmüşse BotanikEOS toolbar'daki Giriş butonuna
        birkaç kez basarak yenile.
        """
        self.log("Oturum düşmüş, yenileniyor...", "warning")
        for deneme in range(3):
            try:
                for elem in self.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "btnMedulayaGirisYap":
                            elem.click_input()
                            self.log(f"Giriş butonu tıklandı ({deneme+1}/3)", "info")
                            break
                    except:
                        pass
            except:
                pass

            time.sleep(4)

            if self.oturum_aktif_mi():
                self.log("Oturum yenilendi!", "success")
                return True

        self.log("Oturum yenilenemedi", "error")
        return False

    def oturumu_kontrol_et_ve_yenile(self):
        """Oturum aktif mi kontrol et, değilse yenile. True dönerse kullanılabilir."""
        if self.oturum_aktif_mi():
            return True
        return self.oturumu_yenile()

    # === REÇETE LİSTESİ OKUMA ===

    def recete_listesi_oku(self):
        """
        Reçete Listesi sayfasındaki reçete numaralarını oku.
        Returns: list[str] - reçete numaraları
        """
        if not self.bagli:
            return []

        receteler = []
        try:
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    # Reçete numaraları 7 karakter ve 3LE ile başlar
                    if len(txt) == 7 and txt.startswith("3LE"):
                        receteler.append(txt)
                except:
                    pass
        except Exception as e:
            self.log(f"Reçete listesi okuma hatası: {e}", "error")

        self.log(f"Reçete listesinde {len(receteler)} reçete bulundu", "info")
        return receteler

    def receteye_tikla(self, recete_no):
        """
        Reçete listesindeki bir reçete numarasına tıkla ve
        reçete sayfasının yüklenmesini bekle (f:buttonGeriDon görünene kadar).
        """
        if not self.bagli:
            return False

        try:
            tiklandi = False
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    if elem.window_text() == recete_no:
                        elem.click_input()
                        tiklandi = True
                        break
                except:
                    pass

            if not tiklandi:
                self.log(f"Reçete bulunamadı: {recete_no}", "error")
                return False

            # Reçete sayfasının ve ilaç tablosunun yüklenmesini bekle
            # Önce f:buttonIlacBilgiGorme, sonra f:tbl1:0:checkbox7 bekle
            sayfa_yuklendi = False
            for bekle in range(15):
                time.sleep(1)
                for elem in self.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "f:buttonIlacBilgiGorme":
                            sayfa_yuklendi = True
                            break
                    except:
                        pass
                if sayfa_yuklendi:
                    break

            if not sayfa_yuklendi:
                self.log(f"Reçete sayfası yüklenemedi: {recete_no}", "error")
                return False

            # İlaç tablosunun yüklenmesini bekle (checkbox görünene kadar)
            for bekle in range(10):
                time.sleep(1)
                for elem in self.main_window.descendants(control_type="CheckBox"):
                    try:
                        if "tbl1" in str(elem.element_info.automation_id):
                            self.log(f"Reçete açıldı: {recete_no}", "info")
                            time.sleep(1)
                            return True
                    except:
                        pass

            # Checkbox bulunamadı ama sayfa yüklendi - devam et
            self.log(f"Reçete açıldı (tablo gecikmeli): {recete_no}", "warning")
            time.sleep(3)
            return True
        except Exception as e:
            self.log(f"Reçete tıklama hatası: {e}", "error")
            return False

    # === REÇETE DETAY OKUMA ===

    def recete_bilgileri_oku(self):
        """
        Açık reçetenin temel bilgilerini oku.
        DataItem'lardan reçete no, hasta adı, kapsam, fatura türü vb.

        Returns:
            dict: Reçete bilgileri
        """
        bilgiler = {
            "recete_no": "",
            "hasta_adi": "",
            "kapsam": "",
            "fatura_turu": "",
            "karekod_durumu": "",
            "e_recete_no": "",
        }

        try:
            items = self.main_window.descendants(control_type="DataItem")
            texts = []
            for item in items:
                try:
                    txt = item.window_text()
                    y = item.rectangle().top
                    if txt.strip() and y > 200 and y < 470:
                        texts.append((txt.strip(), y))
                except:
                    pass

            # Reçete No: 7 karakter, 3LE ile başlar
            for txt, y in texts:
                if len(txt) == 7 and txt.startswith("3LE"):
                    bilgiler["recete_no"] = txt
                elif "Sigortalı" in txt or txt.startswith("4"):
                    bilgiler["kapsam"] = txt
                elif "Grubu" in txt:
                    bilgiler["fatura_turu"] = txt
                elif "Sonlandırıldı" in txt:
                    bilgiler["karekod_durumu"] = txt

            # e-Reçete No
            for txt, y in texts:
                if len(txt) == 7 and not txt.startswith("3LE") and txt[0].isdigit():
                    bilgiler["e_recete_no"] = txt

        except Exception as e:
            self.log(f"Reçete bilgileri okuma hatası: {e}", "error")

        return bilgiler

    def ilac_tablosu_oku(self):
        """
        Açık reçetedeki ilaç tablosunu DataItem'lardan oku.

        İlaç tablosu yapısı (öğrenildi 2026-03-24):
        - DataItem'lar y koordinatına göre satırlara ayrılır
        - Her satırda: Stk/Raf, İlaç Adı, Tutar, Fark, Rapor Kodu, Verilebileceği, Msj
        - Doz bilgisi bir alt satırda: "1 Günde 4 x 2,00 - Adet" formatında
        - Uyarı mesajları daha altta: "Raporsuz VERİLEMEZ..." gibi
        - İlaç satırlarını tespit: x≈936 civarında uzun text (ilaç adı) içerenler

        Returns:
            list[dict]: Her ilaç için bilgi sözlüğü
        """
        ilaclar = []

        try:
            # Tüm DataItem'ları topla (y > 500, ilaç tablosu alanı)
            data_items = []
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    r = elem.rectangle()
                    if txt.strip() and r.top > 500 and r.top < 960:
                        data_items.append({
                            "txt": txt.strip(),
                            "y": r.top,
                            "x": r.left,
                        })
                except:
                    pass

            if not data_items:
                return ilaclar

            # Y koordinatına göre grupla (±8 piksel tolerans)
            satir_gruplari = []
            data_items.sort(key=lambda d: (d["y"], d["x"]))

            current_group = [data_items[0]]
            for item in data_items[1:]:
                if abs(item["y"] - current_group[0]["y"]) < 8:
                    current_group.append(item)
                else:
                    satir_gruplari.append(current_group)
                    current_group = [item]
            satir_gruplari.append(current_group)

            # İlaç satırlarını tespit et: ilaç adı içeren satırlar
            # İlaç adı genellikle x≈936 civarında ve uzun text
            ilac_idx = 0
            for grup in satir_gruplari:
                grup.sort(key=lambda d: d["x"])

                # Bu satırda ilaç adı var mı?
                ilac_adi = ""
                stk_raf = ""
                tutar = ""
                fark = ""
                rapor_kodu = ""
                verilebilecegi = ""
                msj = ""
                doz_str = ""

                for item in grup:
                    txt = item["txt"]
                    x = item["x"]

                    # İlaç adı: uzun text, genellikle x > 900
                    if x > 900 and len(txt) > 10 and any(k in txt.upper() for k in ["MG", "ML", "TABLET", "KAPSUL", "KAPSÜL", "DOZ", "INH", "GARGARA", "ŞURUP", "DAMLA"]):
                        ilac_adi = txt
                    # Stk/Raf: satır numarası + depo kodu, x < 920
                    elif x < 920 and ("\n" in txt or "(" in txt):
                        stk_raf = txt.replace("\n", " ")
                    # Msj: var/yok
                    elif txt.lower() in ["var", "yok"]:
                        msj = txt.lower()
                    # Verilebileceği: tarih formatı
                    elif "/" in txt and len(txt) == 10 and txt[2] == "/":
                        verilebilecegi = txt
                    # Rapor kodu: XX.XX formatı
                    elif "." in txt and len(txt) <= 8 and txt[0].isdigit():
                        rapor_kodu = txt
                    # Tutar/Fark: sayısal değer
                    elif txt.replace(",", "").replace(".", "").replace(" ", "").isdigit():
                        if not tutar:
                            tutar = txt
                        elif not fark:
                            fark = txt
                    # Doz bilgisi: "1 Günde 4 x 2,00 - Adet" formatı
                    elif "Günde" in txt or "Haftada" in txt:
                        doz_str = txt

                if ilac_adi:
                    ilaclar.append({
                        "satir": ilac_idx,
                        "ilac_adi": ilac_adi,
                        "stk_raf": stk_raf,
                        "tutar": tutar,
                        "fark": fark,
                        "rapor_kodu": rapor_kodu,
                        "verilebilecegi": verilebilecegi,
                        "msj": msj,
                        "doz": doz_str,
                    })
                    ilac_idx += 1

                # Doz satırı bir önceki ilaca ait olabilir
                if doz_str and not ilac_adi and ilaclar:
                    ilaclar[-1]["doz"] = doz_str

            # Uyarı mesajlarını ilaçlara ekle
            for grup in satir_gruplari:
                for item in grup:
                    txt = item["txt"]
                    if "VERİLEMEZ" in txt or "KONTROL" in txt or "UZMAN" in txt:
                        # En yakın üst ilaç satırına ekle
                        for ilac in reversed(ilaclar):
                            if item["y"] > 500:
                                if "uyari" not in ilac:
                                    ilac["uyari"] = []
                                ilac["uyari"].append(txt)
                                break

        except Exception as e:
            self.log(f"İlaç tablosu okuma hatası: {e}", "error")

        return ilaclar

    # === REÇETE NAVİGASYON ===

    def sonraki_recete(self):
        """Sonraki Reçete butonuna tıkla"""
        try:
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "f:buttonSonraki":
                        elem.click_input()
                        time.sleep(3)
                        return True
                except:
                    pass
        except:
            pass
        return False

    def onceki_recete(self):
        """Önceki Reçete butonuna tıkla"""
        try:
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "f:buttonOncekiRecete":
                        elem.click_input()
                        time.sleep(3)
                        return True
                except:
                    pass
        except:
            pass
        return False

    def geri_don(self):
        """Geri Dön butonuna tıkla"""
        try:
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "f:buttonGeriDon":
                        elem.click_input()
                        time.sleep(2)
                        return True
                except:
                    pass
        except:
            pass
        return False

    # === İLAÇ BİLGİ OKUMA (f:buttonIlacBilgiGorme) ===

    def ilac_bilgi_oku(self, satir_index):
        """
        Belirli bir ilaç satırının İlaç Bilgi sayfasını aç ve oku.
        Etkin madde, SGK kodu, mesaj, maks doz bilgilerini döndürür.

        AutomationID'ler:
        - Checkbox: f:tbl1:{row}:checkbox7
        - İlaç Bilgi butonu: f:buttonIlacBilgiGorme
        - Geri Dön: form1:buttonGeriDon (İlaç Bilgi sayfasından)

        Args:
            satir_index: İlaç tablosundaki satır indexi (0-4)

        Returns:
            dict: {etkin_madde, sgk_kodu, mesaj_basligi, mesaj_metni,
                   ayaktan_maks_doz, raporlu_maks_doz, rapor_turu, sut_bilgi}
        """
        bilgi = {
            "etkin_madde": "", "sgk_kodu": "", "mesaj_basligi": "",
            "mesaj_metni": "", "ayaktan_maks_doz": "", "raporlu_maks_doz": "",
            "rapor_turu": "", "sut_bilgi": "",
        }

        try:
            # 1. Checkbox seç
            cb_id = f"f:tbl1:{satir_index}:checkbox7"
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == cb_id:
                        elem.click_input()
                        time.sleep(0.3)
                        break
                except:
                    pass

            # 2. İlaç Bilgi butonuna tıkla
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "f:buttonIlacBilgiGorme":
                        elem.click_input()
                        time.sleep(3)
                        break
                except:
                    pass

            # 3. Sayfadaki DataItem'ları oku
            items = []
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    r = elem.rectangle()
                    if txt.strip() and len(txt) < 200:
                        items.append((txt.strip(), r.top))
                except:
                    pass

            # Etkin madde (SGK kodu + isim)
            for txt, y in items:
                if txt.startswith("SGK") and "-" in txt:
                    parts = txt.split("-", 1)
                    bilgi["sgk_kodu"] = parts[0].strip()
                    bilgi["etkin_madde"] = parts[1].strip() if len(parts) > 1 else ""
                elif "Günde" in txt and "x" in txt:
                    # Doz bilgisi - hangisi olduğunu y'ye göre belirle
                    if not bilgi["ayaktan_maks_doz"]:
                        bilgi["ayaktan_maks_doz"] = txt
                    elif not bilgi["raporlu_maks_doz"]:
                        bilgi["raporlu_maks_doz"] = txt

            # Mesaj bilgisi
            for txt, y in items:
                if "4.2." in txt or "SUT" in txt.upper():
                    bilgi["mesaj_basligi"] = txt
                elif "Uzman Hekim Raporu" in txt:
                    bilgi["rapor_turu"] = txt
                elif "Raporlu" in txt or "Raporsuz" in txt:
                    bilgi["sut_bilgi"] = txt

            self.log(f"İlaç Bilgi okundu: {bilgi.get('etkin_madde', '?')}", "info")

            # 4. Geri dön (form1:buttonGeriDon - İlaç Bilgi sayfasının Geri Dön'ü)
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "form1:buttonGeriDon":
                        elem.click_input()
                        time.sleep(2)
                        break
                except:
                    pass

        except Exception as e:
            self.log(f"İlaç Bilgi okuma hatası: {e}", "error")

        return bilgi

    # === RAPOR OKUMA (f:buttonRaporGoruntule) ===

    def rapor_bilgileri_oku(self, satir_index):
        """
        Belirli bir ilaç satırının Rapor sayfasını aç ve oku.

        AutomationID'ler:
        - Checkbox: f:tbl1:{row}:checkbox7
        - Rapor butonu: f:buttonRaporGoruntule
        - Rapor Listesi: f:buttonRaporListesi
        - Geri Dön: form1:buttonGeriDon

        Returns:
            dict: {rapor_no, rapor_tarihi, bitis_tarihi, tesis,
                   doktor, brans, tani_kodu, tani_adi,
                   etkin_maddeler: [{sgk_kodu, etkin_madde, doz}]}
        """
        rapor = {
            "rapor_no": "", "rapor_tarihi": "", "bitis_tarihi": "",
            "tesis": "", "doktor": "", "brans": "",
            "tani_kodu": "", "tani_adi": "",
            "etkin_maddeler": [],
        }

        try:
            # 1. Checkbox seç
            cb_id = f"f:tbl1:{satir_index}:checkbox7"
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == cb_id:
                        elem.click_input()
                        time.sleep(0.3)
                        break
                except:
                    pass

            # 2. Rapor butonuna tıkla
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "f:buttonRaporGoruntule":
                        elem.click_input()
                        time.sleep(4)
                        break
                except:
                    pass

            # 3. Rapor sayfası DataItem'larını oku
            items = []
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    r = elem.rectangle()
                    if txt.strip() and r.top > 100 and len(txt) < 200:
                        items.append((txt.strip(), r.top, r.left))
                except:
                    pass

            # Parse et
            for txt, y, x in items:
                # Rapor numarası
                if y > 290 and y < 320 and txt.isdigit() and len(txt) <= 6:
                    rapor["rapor_no"] = txt
                # Tarihler
                elif "/" in txt and len(txt) == 10 and txt[2] == "/":
                    if not rapor["rapor_tarihi"]:
                        rapor["rapor_tarihi"] = txt
                    elif not rapor["bitis_tarihi"]:
                        rapor["bitis_tarihi"] = txt
                # Tesis
                elif "HASTANE" in txt.upper() or "DEVLET" in txt.upper():
                    rapor["tesis"] = txt
                # Tanı kodu ve adı
                elif txt.startswith("J") or txt.startswith("E") or txt.startswith("N") or txt.startswith("I"):
                    if "." in txt and len(txt) <= 6:
                        rapor["tani_kodu"] = txt
                    elif len(txt) > 10:
                        rapor["tani_adi"] = txt
                # Rapor kodu + tanı açıklaması (ör: "05.02 - Kronik...")
                elif " - " in txt and txt[0].isdigit():
                    parts = txt.split(" - ", 1)
                    rapor["tani_kodu"] = rapor["tani_kodu"] or parts[0].strip()
                    rapor["tani_adi"] = rapor["tani_adi"] or (parts[1].strip() if len(parts) > 1 else "")
                # Branş
                elif "Hastalıkları" in txt or "Hekimi" in txt:
                    rapor["brans"] = txt
                # Etkin madde + doz (rapor etkin madde bilgileri bölümü)
                elif txt.startswith("SGK"):
                    rapor["etkin_maddeler"].append({
                        "sgk_kodu": txt,
                        "etkin_madde": "",
                        "doz": "",
                    })
                elif "Günde" in txt and "x" in txt and rapor["etkin_maddeler"]:
                    rapor["etkin_maddeler"][-1]["doz"] = txt

            # Etkin madde isimlerini eşleştir
            etkin_madde_texts = [txt for txt, y, x in items
                                if len(txt) > 10 and any(k in txt.upper() for k in
                                ["FORMOTEROL", "TIOTROPIUM", "SALBUTAMOL", "PIOGLITAZON",
                                 "METFORMIN", "INSULIN", "BEKLOMETAZON", "VILANTEROL",
                                 "FLUTIKAZON", "TEOFILIN", "UMEKLIDINYUM"])]
            for i, em in enumerate(rapor["etkin_maddeler"]):
                if i < len(etkin_madde_texts):
                    em["etkin_madde"] = etkin_madde_texts[i]

            self.log(f"Rapor okundu: {rapor['tani_kodu']} - {len(rapor['etkin_maddeler'])} etkin madde", "info")

            # 4. Geri dön
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "form1:buttonGeriDon":
                        elem.click_input()
                        time.sleep(2)
                        break
                except:
                    pass

        except Exception as e:
            self.log(f"Rapor okuma hatası: {e}", "error")

        return rapor

    # === İLAÇ GEÇMİŞİ OKUMA (f:buttonIlacListesi) ===

    def ilac_gecmisi_oku(self):
        """
        İlaç Geçmişi (Kullanılan İlaç Listesi) sayfasını aç ve oku.

        AutomationID'ler:
        - İlaç butonu: f:buttonIlacListesi
        - Geri Dön: form1:buttonGeriDon
        - Göz İlaçları: form1:buttonGozIlacListesi

        Returns:
            list[dict]: {recete_no, ilac_adi, barkod, recete_tarihi,
                        ilac_alim_tarihi, verilebilecegi, doz, rapor_kodu,
                        etkin_madde}
        """
        gecmis = []

        try:
            # 1. İlaç butonuna tıkla
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "f:buttonIlacListesi":
                        elem.click_input()
                        time.sleep(4)
                        break
                except:
                    pass

            # 2. DataItem'ları oku
            items = []
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    r = elem.rectangle()
                    if txt.strip() and r.top > 450 and len(txt) < 200:
                        items.append((txt.strip(), r.top, r.left))
                except:
                    pass

            # Y koordinatına göre grupla
            items.sort(key=lambda x: (x[1], x[2]))

            # Her satır bir ilaç kaydı (reçete no ile başlar)
            current = None
            for txt, y, x in items:
                # Reçete no (7 karakter, 3LE ile başlar)
                if len(txt) == 7 and txt.startswith("3LE") and x < 700:
                    if current:
                        gecmis.append(current)
                    current = {
                        "recete_no": txt, "ilac_adi": "", "barkod": "",
                        "recete_tarihi": "", "ilac_alim_tarihi": "",
                        "verilebilecegi": "", "doz": "", "rapor_kodu": "",
                        "etkin_madde": "",
                    }
                elif current:
                    # İlaç adı (uzun, parantez içinde barkod)
                    if "(" in txt and ")" in txt and len(txt) > 20:
                        # "VENTOLIN INHALER 200 DOZ (SABA)(8699522521456)"
                        current["ilac_adi"] = txt
                    # Tarih
                    elif "/" in txt and len(txt) == 10 and txt[2] == "/":
                        if not current["recete_tarihi"]:
                            current["recete_tarihi"] = txt
                        elif not current["ilac_alim_tarihi"]:
                            current["ilac_alim_tarihi"] = txt
                        elif not current["verilebilecegi"]:
                            current["verilebilecegi"] = txt
                    # Doz
                    elif "Günde" in txt and "x" in txt:
                        current["doz"] = txt
                    # Rapor kodu
                    elif " - " in txt and txt[:5].replace(".", "").isdigit():
                        current["rapor_kodu"] = txt
                    # Etkin madde (SGK kodu veya uzun isim)
                    elif txt.startswith("SGK") or (len(txt) > 15 and any(k in txt.upper() for k in
                            ["FORMOTEROL", "TIOTROPIUM", "SALBUTAMOL", "PIOGLITAZON",
                             "METFORMIN", "BROMUR", "FUMARAT"])):
                        current["etkin_madde"] = txt

            if current:
                gecmis.append(current)

            self.log(f"İlaç geçmişi: {len(gecmis)} kayıt", "info")

            # 3. Geri dön
            for elem in self.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "form1:buttonGeriDon":
                        elem.click_input()
                        time.sleep(2)
                        break
                except:
                    pass

        except Exception as e:
            self.log(f"İlaç geçmişi okuma hatası: {e}", "error")

        return gecmis


class ReceteRaporKontrolGUI:
    """Reçete/Rapor Kontrol ana ekranı"""

    def __init__(self, root, ana_menu_callback=None):
        self.root = root
        self.ana_menu_callback = ana_menu_callback
        self.root.title("Reçete / Rapor Kontrol")
        self.root.geometry("750x650")
        self.root.configure(bg="#1E3A5F")

        # Log alanı (önce oluştur ki MedulaBaglanti kullanabilsin)
        self.log_text = None

        # Medula bağlantısı
        self.medula = MedulaBaglanti(log_callback=self.log_yaz)

        # Kontrol durumu
        self.kontrol_aktif = False
        self.aktif_grup = None

        # Grup durumlarını yükle
        self.grup_durumlari = self._durumlari_yukle()

        # GUI referansları
        self.grup_labels = {}
        self.grup_butonlari = {}
        self.durum_labels = {}
        self.medula_durum_label = None

        self._gui_olustur()

        # Başlangıçta Medula durumunu kontrol et
        self.root.after(500, self._medula_durumu_kontrol)

    def _durumlari_yukle(self):
        """Grup durumlarını JSON'dan yükle"""
        varsayilan = {}
        for g in GRUP_TANIMLARI:
            varsayilan[g["kod"]] = {
                "son_recete": "",
                "toplam_kontrol": 0,
                "son_kontrol_tarihi": None,
            }

        if os.path.exists(DURUM_DOSYASI):
            try:
                with open(DURUM_DOSYASI, "r", encoding="utf-8") as f:
                    kaydedilen = json.load(f)
                for kod in varsayilan:
                    if kod not in kaydedilen:
                        kaydedilen[kod] = varsayilan[kod]
                return kaydedilen
            except Exception as e:
                logger.error(f"Durum dosyası yükleme hatası: {e}")

        return varsayilan

    def _durumlari_kaydet(self):
        """Grup durumlarını JSON'a kaydet"""
        try:
            with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.grup_durumlari, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Durum kaydetme hatası: {e}")

    def _gui_olustur(self):
        """Ana GUI'yi oluştur"""
        # === BAŞLIK ===
        baslik_frame = tk.Frame(self.root, bg="#0D2137", height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame, text="Reçete / Rapor Kontrol",
            font=("Segoe UI", 16, "bold"), fg="white", bg="#0D2137"
        ).pack(side="left", padx=15, pady=10)

        geri_btn = tk.Button(
            baslik_frame, text="<- Ana Menü", font=("Segoe UI", 10),
            fg="white", bg="#455A64", activebackground="#37474F",
            bd=0, padx=10, pady=5, command=self._ana_menuye_don
        )
        geri_btn.pack(side="right", padx=15, pady=10)

        # === MEDULA BAĞLANTI BÖLÜMÜ ===
        medula_frame = tk.Frame(self.root, bg="#263238")
        medula_frame.pack(fill="x", padx=15, pady=(10, 5))

        medula_btn = tk.Button(
            medula_frame, text="MEDULA Bağlan",
            font=("Segoe UI", 10, "bold"),
            fg="white", bg="#0277BD", activebackground="#01579B",
            bd=0, padx=12, pady=6, cursor="hand2",
            command=self._medula_baglan_tikla
        )
        medula_btn.pack(side="left", padx=5, pady=5)
        self.medula_btn = medula_btn

        self.medula_durum_label = tk.Label(
            medula_frame, text="Durum: Kontrol ediliyor...",
            font=("Segoe UI", 9), fg="#90A4AE", bg="#263238"
        )
        self.medula_durum_label.pack(side="left", padx=10)

        # === İÇERİK ===
        icerik_frame = tk.Frame(self.root, bg="#1E3A5F")
        icerik_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # Tümünü Kontrol Et butonu
        tumunu_btn = tk.Button(
            icerik_frame,
            text="TÜMÜNÜ KONTROL ET",
            font=("Segoe UI", 14, "bold"),
            fg="white", bg="#00695C", activebackground="#004D40",
            bd=0, padx=20, pady=12, cursor="hand2",
            command=self._tumunu_kontrol_et
        )
        tumunu_btn.pack(fill="x", pady=(0, 8))
        self.tumunu_btn = tumunu_btn

        # Ayırıcı
        tk.Frame(icerik_frame, bg="#3D5A80", height=2).pack(fill="x", pady=3)

        # Grup butonları
        for grup in GRUP_TANIMLARI:
            self._grup_satiri_olustur(icerik_frame, grup)

        # Ayırıcı
        tk.Frame(icerik_frame, bg="#3D5A80", height=2).pack(fill="x", pady=3)

        # Seçenekler satırı
        secenek_frame = tk.Frame(icerik_frame, bg="#1E3A5F")
        secenek_frame.pack(fill="x", pady=3)

        self.bastan_var = tk.BooleanVar(value=False)
        bastan_cb = tk.Checkbutton(
            secenek_frame, text="Baştan başla (kaldığı yerden değil)",
            variable=self.bastan_var,
            fg="#87CEEB", bg="#1E3A5F", selectcolor="#2C4A6E",
            activebackground="#1E3A5F", activeforeground="#87CEEB",
            font=("Segoe UI", 10)
        )
        bastan_cb.pack(side="left")

        temizle_btn = tk.Button(
            secenek_frame, text="Hafızayı Temizle",
            font=("Segoe UI", 9), fg="white", bg="#B71C1C",
            activebackground="#7F0000", bd=0, padx=10, pady=3,
            command=self._hafizayi_temizle
        )
        temizle_btn.pack(side="right")

        # === LOG ALANI ===
        log_frame = tk.Frame(icerik_frame, bg="#0D2137", bd=1, relief="sunken")
        log_frame.pack(fill="both", expand=True, pady=(8, 0))

        tk.Label(
            log_frame, text="Kontrol Günlüğü",
            font=("Segoe UI", 9, "bold"), fg="#87CEEB", bg="#0D2137"
        ).pack(anchor="w", padx=5, pady=2)

        self.log_text = tk.Text(
            log_frame, font=("Consolas", 9), fg="#E0E0E0", bg="#0D2137",
            insertbackground="white", wrap="word", height=10,
            state="disabled", bd=0
        )
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=2)

        # Tag'ler
        self.log_text.tag_configure("info", foreground="#87CEEB")
        self.log_text.tag_configure("success", foreground="#4CAF50")
        self.log_text.tag_configure("warning", foreground="#FF9800")
        self.log_text.tag_configure("error", foreground="#F44336")
        self.log_text.tag_configure("header", foreground="#FFFFFF", font=("Consolas", 10, "bold"))

    def _grup_satiri_olustur(self, parent, grup):
        """Tek bir grup için buton + durum label satırı"""
        satir = tk.Frame(parent, bg="#1E3A5F")
        satir.pack(fill="x", pady=3)

        kod = grup["kod"]
        durum = self.grup_durumlari.get(kod, {})
        son_recete = durum.get("son_recete", "")
        toplam = durum.get("toplam_kontrol", 0)

        btn = tk.Button(
            satir,
            text=f"  {grup['ad']}",
            font=("Segoe UI", 11, "bold"),
            fg="white", bg=grup["renk"], activebackground=grup["hover"],
            bd=0, padx=15, pady=8, width=22, anchor="w", cursor="hand2",
            command=lambda k=kod: self._grup_kontrol_baslat(k)
        )
        btn.pack(side="left")
        self.grup_butonlari[kod] = btn

        durum_text = f"Son: {son_recete}" if son_recete else "Henüz başlanmadı"
        if toplam > 0:
            durum_text += f"  |  {toplam} reçete kontrol edildi"

        durum_lbl = tk.Label(
            satir, text=durum_text,
            font=("Segoe UI", 9), fg="#87CEEB", bg="#1E3A5F"
        )
        durum_lbl.pack(side="left", padx=10)
        self.durum_labels[kod] = durum_lbl

    def _durum_label_guncelle(self, kod):
        """Bir grubun durum label'ını güncelle"""
        if kod not in self.durum_labels:
            return
        durum = self.grup_durumlari.get(kod, {})
        son_recete = durum.get("son_recete", "")
        toplam = durum.get("toplam_kontrol", 0)

        durum_text = f"Son: {son_recete}" if son_recete else "Henüz başlanmadı"
        if toplam > 0:
            durum_text += f"  |  {toplam} reçete kontrol edildi"

        self.durum_labels[kod].config(text=durum_text)

    # === MEDULA BAĞLANTI ===

    def _medula_durumu_kontrol(self):
        """
        Başlangıçta Medula durumunu kontrol et ve otomatik bağlan.
        Bağlandıktan sonra oturum aktif mi kontrol et.
        Düşmüşse taskkill + yeniden başlat.
        """
        self.log_yaz("Medula kontrol ediliyor...", "info")
        self.medula_durum_label.config(text="Durum: Kontrol ediliyor...", fg="#FF9800")
        self.root.update()

        def otomatik_baglan():
            basarili = self.medula.medula_ac_ve_baglan()

            if basarili:
                # Sayfa yüklenmesi için bekle
                time.sleep(5)
                # Birkaç kez oturum kontrol
                oturum_ok = False
                for _ in range(3):
                    if self.medula.oturum_aktif_mi():
                        oturum_ok = True
                        break
                    time.sleep(3)

                if oturum_ok:
                    self.root.after(0, lambda: self._medula_baglanti_sonuc(True))
                    return

                # Oturum düşmüş - Giriş butonuna basarak yenile
                self.root.after(0, lambda: self.log_yaz("Oturum düşmüş, Giriş butonu ile yenileniyor...", "warning"))
                for deneme in range(4):
                    if self.medula.main_window:
                        for elem in self.medula.main_window.descendants():
                            try:
                                if elem.element_info.automation_id == "btnMedulayaGirisYap":
                                    elem.click_input()
                                    break
                            except:
                                pass
                    time.sleep(4)
                    if self.medula.oturum_aktif_mi():
                        self.root.after(0, lambda: self._medula_baglanti_sonuc(True))
                        return

            if basarili and not self.medula.oturum_aktif_mi():
                # Giriş butonu da işe yaramadı - tam restart
                self.root.after(0, lambda: self.log_yaz("Tam restart yapılıyor...", "warning"))
                self.medula.keepalive_durdur()
                self.medula._medula_kapat()
                self.medula.bagli = False
                self.medula.main_window = None
                self.medula.medula_hwnd = None
                time.sleep(3)
                basarili = self.medula._exe_baslat_ve_giris_yap()

            self.root.after(0, lambda: self._medula_baglanti_sonuc(basarili))

        threading.Thread(target=otomatik_baglan, daemon=True).start()

    def _medula_baglan_tikla(self):
        """Medula bağlan/aç butonuna tıklandı (manuel tetikleme)"""
        if self.medula.bagli:
            self.log_yaz("Medula zaten bağlı", "info")
            return

        self.log_yaz("Medula'ya bağlanılıyor...", "info")
        self.medula_durum_label.config(text="Durum: İşlem yapılıyor...", fg="#FF9800")
        self.root.update()

        def islem():
            basarili = self.medula.medula_ac_ve_baglan()
            self.root.after(0, lambda: self._medula_baglanti_sonuc(basarili))

        threading.Thread(target=islem, daemon=True).start()

    def _medula_baglanti_sonuc(self, basarili):
        """Medula bağlantı sonucunu GUI'ye yansıt"""
        if basarili:
            self.medula_durum_label.config(text="Durum: Bağlı", fg="#4CAF50")
            self.medula_btn.config(text="MEDULA Bağlı", bg="#2E7D32")
            self.log_yaz("Medula'ya bağlantı kuruldu!", "success")
        else:
            self.medula_durum_label.config(text="Durum: Bağlantı başarısız", fg="#F44336")
            self.medula_btn.config(text="MEDULA Bağlan", bg="#D32F2F")
            self.log_yaz("Medula bağlantısı kurulamadı! Butona basarak tekrar deneyin.", "error")

    # === LOG ===

    def log_yaz(self, mesaj, tag="info"):
        """Log alanına mesaj yaz"""
        if not self.log_text:
            return
        self.log_text.config(state="normal")
        zaman = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{zaman}] {mesaj}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # === KONTROL FONKSİYONLARI ===

    def _medula_hazir_mi(self):
        """Medula bağlı mı kontrol et, değilse otomatik bağlan. True dönerse hazır."""
        if self.medula.bagli:
            return True

        self.log_yaz("Medula bağlı değil, otomatik bağlanılıyor...", "warning")
        self.medula_durum_label.config(text="Durum: Bağlanılıyor...", fg="#FF9800")
        self.root.update()

        basarili = self.medula.medula_ac_ve_baglan()
        self._medula_baglanti_sonuc(basarili)
        return basarili

    def _tumunu_kontrol_et(self):
        """Tüm grupları sırayla kontrol et: C -> A -> B -> CK -> GK"""
        if self.kontrol_aktif:
            self.log_yaz("Zaten bir kontrol devam ediyor!", "warning")
            return

        self.log_yaz("=" * 40, "header")
        self.log_yaz("TÜMÜNÜ KONTROL ET başlatılıyor...", "header")
        self.log_yaz("Sıra: C -> A -> B -> C Kan Ürünü -> Geçici Koruma", "info")
        self.log_yaz("=" * 40, "header")

        def kontrol_thread():
            self.kontrol_aktif = True
            try:
                for grup in GRUP_TANIMLARI:
                    if not self.kontrol_aktif:
                        break
                    self._grup_kontrol_islemi(grup["kod"])
            finally:
                self.kontrol_aktif = False
                self.root.after(0, lambda: self.log_yaz("Tüm kontroller tamamlandı", "header"))

        threading.Thread(target=kontrol_thread, daemon=True).start()

    def _grup_kontrol_baslat(self, grup_kodu):
        """Belirli bir grubun kontrolünü başlat"""
        if self.kontrol_aktif:
            self.log_yaz("Zaten bir kontrol devam ediyor!", "warning")
            return

        def kontrol_thread():
            self.kontrol_aktif = True
            try:
                self._grup_kontrol_islemi(grup_kodu)
            finally:
                self.kontrol_aktif = False

        threading.Thread(target=kontrol_thread, daemon=True).start()

    def _grup_kontrol_islemi(self, grup_kodu):
        """
        Bir grubun tam kontrol akışı (thread içinde çalışır):
        1. Medula bağlan
        2. Reçete Listesi → Grup seç → Sorgula
        3. Her reçeteyi aç → İlaçları oku → Kontrol et → Sonraki
        """
        from recete_kontrol_motoru import ReceteKontrolMotoru, KontrolSonuc

        bastan = self.bastan_var.get()
        durum = self.grup_durumlari.get(grup_kodu, {})
        son_recete = durum.get("son_recete", "")
        grup_adi = next((g["ad"] for g in GRUP_TANIMLARI if g["kod"] == grup_kodu), grup_kodu)

        self.root.after(0, lambda: self.log_yaz(f"{'─' * 30}", "info"))
        self.root.after(0, lambda: self.log_yaz(f"{grup_adi} kontrolü başlatılıyor...", "header"))

        # 1. Medula bağlan ve oturum kontrol
        # Her zaman: bağlı değilse bağlan, oturum düşmüşse restart
        def medula_hazirla():
            """Medula'yı kullanıma hazır hale getir. True dönerse hazır."""
            # Bağlı değilse bağlan
            if not self.medula.bagli:
                basarili = self.medula.medula_ac_ve_baglan()
                self.root.after(0, lambda: self._medula_baglanti_sonuc(basarili))
                if not basarili:
                    return False
                # Yeni giriş sonrası sayfa yüklenmesi için bekle
                time.sleep(5)

            # Oturum aktif mi? (birkaç kez dene - sayfa yüklenme süresi)
            for _ in range(3):
                if self.medula.oturum_aktif_mi():
                    return True
                time.sleep(3)

            # Oturum düşmüş - önce Giriş butonuna basarak yenilemeyi dene
            self.root.after(0, lambda: self.log_yaz("Oturum düşmüş, Giriş butonu ile yenileniyor...", "warning"))

            for deneme in range(4):
                # Giriş butonuna bas
                for elem in self.medula.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "btnMedulayaGirisYap":
                            elem.click_input()
                            self.root.after(0, lambda d=deneme: self.log_yaz(f"Giriş butonu tıklandı ({d+1}/4)", "info"))
                            break
                    except:
                        pass
                time.sleep(4)

                if self.medula.oturum_aktif_mi():
                    self.root.after(0, lambda: self.log_yaz("Oturum yenilendi!", "success"))
                    return True

            # Giriş butonu işe yaramadı - tam restart
            self.root.after(0, lambda: self.log_yaz("Giriş butonu ile yenilenemedi, tam restart...", "warning"))
            self.medula.keepalive_durdur()
            self.medula._medula_kapat()
            self.medula.bagli = False
            self.medula.main_window = None
            self.medula.medula_hwnd = None
            time.sleep(3)

            basarili = self.medula._exe_baslat_ve_giris_yap()
            self.root.after(0, lambda b=basarili: self._medula_baglanti_sonuc(b))
            if not basarili:
                return False

            time.sleep(5)
            for _ in range(3):
                if self.medula.oturum_aktif_mi():
                    return True
                time.sleep(3)

            return self.medula.oturum_aktif_mi()

        if not medula_hazirla():
            self.root.after(0, lambda: self.log_yaz("Medula hazırlanamadı!", "error"))
            return

        # 2. Reçete Listesi → Grup → Sorgula
        self.medula.recete_listesine_git()
        time.sleep(1)
        self.medula.grup_sekmesine_tikla(grup_kodu)
        time.sleep(1)
        self.medula.sorgula()
        time.sleep(2)

        # 3. Reçete listesini oku
        receteler = self.medula.recete_listesi_oku()
        if not receteler:
            self.root.after(0, lambda: self.log_yaz(f"{grup_adi}: Reçete bulunamadı", "warning"))
            return

        self.root.after(0, lambda: self.log_yaz(
            f"{grup_adi}: {len(receteler)} reçete bulundu", "info"))

        # Kaldığı yerden devam mı?
        baslangic_idx = 0
        if not bastan and son_recete and son_recete in receteler:
            baslangic_idx = receteler.index(son_recete)
            self.root.after(0, lambda: self.log_yaz(
                f"Kaldığı yerden devam: {son_recete} (#{baslangic_idx + 1})", "info"))

        # 4. Kontrol motoru
        motor = ReceteKontrolMotoru(log_callback=lambda msg, tag="info": self.root.after(0, lambda m=msg, t=tag: self.log_yaz(m, t)))

        # 5. Her reçeteyi kontrol et
        for idx in range(baslangic_idx, len(receteler)):
            if not self.kontrol_aktif:
                self.root.after(0, lambda: self.log_yaz("Kontrol durduruldu", "warning"))
                break

            recete_no = receteler[idx]
            sira = idx + 1
            self.root.after(0, lambda r=recete_no, s=sira: self.log_yaz(
                f"\n{'═' * 35}", "header"))
            self.root.after(0, lambda r=recete_no, s=sira, t=len(receteler): self.log_yaz(
                f"Reçete {s}/{t}: {r}", "header"))

            # Reçeteye tıkla
            self.medula.receteye_tikla(recete_no)
            time.sleep(2)

            # İlaç tablosunu oku
            ilaclar = self.medula.ilac_tablosu_oku()
            if not ilaclar:
                self.root.after(0, lambda r=recete_no: self.log_yaz(
                    f"  {r}: İlaç bulunamadı, atlanıyor", "warning"))
                self.medula.geri_don()
                time.sleep(1)
                continue

            self.root.after(0, lambda n=len(ilaclar): self.log_yaz(
                f"  {n} ilaç bulundu", "info"))

            # Her ilaç için İlaç Bilgi'den etkin madde oku (veritabanında yoksa)
            for i, ilac in enumerate(ilaclar):
                if not self.kontrol_aktif:
                    break

                # İlaç Bilgi'den etkin madde bilgisini al
                bilgi = self.medula.ilac_bilgi_oku(i)
                if bilgi.get("etkin_madde"):
                    ilac["etkin_madde"] = bilgi["etkin_madde"]
                    ilac["sgk_kodu"] = bilgi.get("sgk_kodu", "")

                    # Yeni etkin maddeyi veritabanına öğret
                    kural = motor.kural_bul(bilgi["etkin_madde"])
                    if not kural and bilgi.get("sgk_kodu"):
                        kural = motor.kural_bul_sgk_kodu(bilgi["sgk_kodu"])

                    if not kural:
                        rapor_gerekli = 1 if ilac.get("rapor_kodu") else 0
                        motor.yeni_kural_ekle(
                            etkin_madde=bilgi["etkin_madde"],
                            sgk_kodu=bilgi.get("sgk_kodu", ""),
                            rapor_kodu=ilac.get("rapor_kodu", ""),
                            rapor_gerekli=rapor_gerekli,
                            kontrol_tipi="rapor_kontrolu" if rapor_gerekli else "raporsuz_verilebilir",
                            aciklama=f"Otomatik öğrenildi: {ilac['ilac_adi']}"
                        )

                time.sleep(0.5)  # Oturum düşmesin diye kısa bekle

            # Algoritmik kontrol
            sonuclar = motor.recete_kontrol(ilaclar)

            # Sonuç özeti
            uygun = sum(1 for s in sonuclar if s.durum == KontrolSonuc.UYGUN)
            sorunlu = sum(1 for s in sonuclar if s.durum == KontrolSonuc.UYGUN_DEGIL)
            kontrol = sum(1 for s in sonuclar if s.durum == KontrolSonuc.KONTROL_GEREKLI)

            ozet_tag = "success" if sorunlu == 0 else "error"
            self.root.after(0, lambda u=uygun, s=sorunlu, k=kontrol, t=ozet_tag: self.log_yaz(
                f"  Sonuç: {u} uygun, {s} sorunlu, {k} kontrol gerekli", t))

            # Durumu kaydet
            self.root.after(0, lambda r=recete_no, g=grup_kodu: self.grup_durumu_guncelle(g, r))

            # Geri dön (reçete listesine)
            self.medula.geri_don()
            time.sleep(1)

        motor.kapat()
        self.root.after(0, lambda g=grup_adi: self.log_yaz(
            f"{g} kontrolü tamamlandı!", "success"))

    def _hafizayi_temizle(self):
        """Tüm grup hafızalarını temizle"""
        cevap = messagebox.askyesno(
            "Hafızayı Temizle",
            "Tüm grup kontrol hafızaları temizlenecek.\nDevam etmek istiyor musunuz?"
        )
        if cevap:
            for kod in self.grup_durumlari:
                self.grup_durumlari[kod] = {
                    "son_recete": "",
                    "toplam_kontrol": 0,
                    "son_kontrol_tarihi": None,
                }
            self._durumlari_kaydet()
            for kod in self.durum_labels:
                self._durum_label_guncelle(kod)
            self.log_yaz("Hafıza temizlendi", "success")

    def _ana_menuye_don(self):
        """Ana menüye geri dön"""
        self.root.destroy()
        if self.ana_menu_callback:
            self.ana_menu_callback()

    def grup_durumu_guncelle(self, grup_kodu, son_recete, toplam_kontrol_arttir=1):
        """Bir grubun durumunu güncelle ve kaydet"""
        if grup_kodu not in self.grup_durumlari:
            self.grup_durumlari[grup_kodu] = {"son_recete": "", "toplam_kontrol": 0, "son_kontrol_tarihi": None}

        self.grup_durumlari[grup_kodu]["son_recete"] = son_recete
        self.grup_durumlari[grup_kodu]["toplam_kontrol"] += toplam_kontrol_arttir
        self.grup_durumlari[grup_kodu]["son_kontrol_tarihi"] = datetime.now().isoformat()
        self._durumlari_kaydet()
        self._durum_label_guncelle(grup_kodu)
