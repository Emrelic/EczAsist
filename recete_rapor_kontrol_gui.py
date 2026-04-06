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
    GIRIS_BEKLEME = 2          # Her giriş denemesi arası bekleme (sn)
    EXE_ACILMA_BEKLEME = 5     # Exe başlatıldıktan sonra minimum bekleme (sn)
    KEEPALIVE_ARALIK = 30      # Oturum canlı tutma aralığı (saniye)

    def __init__(self, log_callback=None):
        self.main_window = None
        self.medula_hwnd = None
        self.bagli = False
        self.log = log_callback or (lambda msg, tag="info": logger.info(msg))
        self._keepalive_thread = None
        self._keepalive_aktif = False
        self._son_aktivite = time.time()

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
                # BotanikEOS penceresine dokunulmuyor - sadece MEDULA aranır

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
        Medula'yı aç ve bağlan.
        SADECE MEDULA penceresi aranır - BotanikEOS'a dokunulmaz.
        """
        import subprocess as sp

        # MEDULA penceresi açık mı?
        sonuc = self._pencereleri_tara()
        if sonuc["medula"]:
            self.log("Medula zaten açık, bağlanılıyor...", "info")
            return self.medula_baglan()

        # MEDULA yok - BotanikMedula.exe başlat → giriş penceresi → giriş yap → MEDULA bekle
        self.log("MEDULA penceresi yok, BotanikMedula.exe başlatılıyor...", "info")
        try:
            sp.Popen([MEDULA_EXE], cwd=os.path.dirname(MEDULA_EXE))
        except Exception as e:
            self.log(f"BotanikMedula.exe başlatılamadı: {e}", "error")
            return False

        # Giriş penceresi (SifreSorForm) açılana kadar bekle
        from pywinauto import Desktop
        giris_win = None
        for i in range(20):
            time.sleep(1)
            try:
                desktop = Desktop(backend="uia")
                for w in desktop.windows():
                    try:
                        if w.element_info.automation_id == "SifreSorForm":
                            giris_win = w
                            self.log(f"Giriş penceresi açıldı ({i+1} sn)", "info")
                            break
                    except:
                        pass
                if giris_win:
                    break
            except:
                pass

        if giris_win:
            # Kullanıcı seç + şifre gir + giriş yap
            try:
                import pyautogui
                pyautogui.FAILSAFE = False
                giris_win.set_focus()
                time.sleep(0.3)
                # Kullanıcı combobox
                combo = giris_win.child_window(auto_id="cmbKullanicilar")
                combo.click_input()
                time.sleep(0.3)
                # "16-botan" kullanıcısını seç
                for item in combo.children():
                    try:
                        if "botan" in item.window_text().lower():
                            item.click_input()
                            self.log("Kullanıcı seçildi: botan", "info")
                            break
                    except:
                        pass
                time.sleep(0.3)
                # Şifre
                sifre = giris_win.child_window(auto_id="txtSifre")
                sifre.click_input()
                time.sleep(0.1)
                sifre.type_keys(MEDULA_SIFRE, with_spaces=True)
                time.sleep(0.1)
                # Giriş butonu
                giris_win.child_window(auto_id="btnGirisYap").click_input()
                self.log("Giriş yapılıyor...", "info")
            except Exception as e:
                self.log(f"Giriş hatası: {e}", "error")

        # MEDULA penceresi açılana kadar bekle
        for i in range(30):
            time.sleep(1)
            sonuc = self._pencereleri_tara()
            if sonuc["medula"]:
                self.log(f"MEDULA açıldı ({i+1} sn), bağlanılıyor...", "info")
                return self.medula_baglan()
        self.log("MEDULA açılamadı!", "error")
        return False

    # === EXE BAŞLATMA ===

    def _exe_baslat_ve_giris_yap(self):
        """Exe'yi başlat, giriş penceresi çıkınca hemen giriş yap."""
        if not os.path.exists(MEDULA_EXE):
            self.log(f"Medula exe bulunamadı: {MEDULA_EXE}", "error")
            return False

        self.log("Medula başlatılıyor...", "info")
        subprocess.Popen([MEDULA_EXE])

        # Sabit bekleme yerine giriş penceresi görünene kadar bekle
        from pywinauto import Desktop
        for i in range(20):  # max 20 sn
            time.sleep(1)
            try:
                desktop = Desktop(backend="uia")
                for w in desktop.windows():
                    try:
                        title = w.window_text()
                        if "BotanikEOS" in title and "(T)" in title and "MEDULA" not in title:
                            self.log(f"Giriş penceresi göründü ({i+1} sn)", "info")
                            break
                    except Exception:
                        continue
                else:
                    continue
                break
            except Exception:
                continue
        else:
            self.log("Giriş penceresi açılmadı, yine de giriş deneniyor...", "warning")

        basarili = self._giris_yap()
        if basarili:
            return True

        # Son şans: taskkill ve tekrar dene
        self.log("Giriş başarısız, taskkill ile kapatılıp tekrar deneniyor...", "warning")
        self._medula_kapat()
        time.sleep(2)

        self.log("Medula tekrar başlatılıyor...", "info")
        subprocess.Popen([MEDULA_EXE])
        time.sleep(self.EXE_ACILMA_BEKLEME)

        return self._giris_yap()

    # === GİRİŞ ===

    def _giris_yap(self):
        """
        Giriş penceresini bul, kullanıcı seç, şifre gir, giriş butonuna bas.
        Hızlı akış: kullanıcı → şifre → enter ard arda yapılır.
        """
        try:
            from pywinauto import Desktop
            import pyautogui

            desktop = Desktop(backend="uia")
            time.sleep(0.5)

            # Giriş penceresini bul
            giris_window = self._giris_penceresi_bul(desktop)
            if not giris_window:
                return False

            giris_window.set_focus()
            time.sleep(0.3)

            # 1. Kullanıcı seç
            if not self._kullanici_sec(giris_window):
                return False

            # 2. Şifre gir
            if not self._sifre_gir(giris_window):
                return False

            # 3. Hemen giriş butonuna bas (bekleme yok)
            try:
                giris_btn = giris_window.child_window(auto_id=MEDULA_IDS["giris_butonu"])
                giris_btn.click_input()
                self.log("Giriş butonuna basıldı", "info")
            except Exception as e:
                self.log(f"Giriş butonu tıklanamadı: {e}", "warning")

            # 4. MEDULA penceresinin açılmasını bekle (poll ile, sabit bekleme yok)
            for deneme in range(self.MAX_GIRIS_DENEME * 5):  # ~20 sn max
                time.sleep(1)
                sonuc = self._pencereleri_tara()
                if sonuc["medula"]:
                    self.log("Medula açıldı!", "success")
                    return self.medula_baglan()

                # Her 5 sn'de bir giriş butonuna tekrar bas (pencere açılmadıysa)
                if deneme > 0 and deneme % 5 == 0:
                    self.log(f"Medula henüz açılmadı, giriş tekrar deneniyor...", "info")
                    try:
                        giris_window = self._giris_penceresi_bul(desktop, max_bekleme=2)
                        if giris_window:
                            giris_btn = giris_window.child_window(auto_id=MEDULA_IDS["giris_butonu"])
                            giris_btn.click_input()
                    except Exception:
                        pass

            self.log(f"Medula açılamadı", "error")
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
            time.sleep(0.3)

            items = combo.descendants(control_type="ListItem")
            for item in items:
                try:
                    if "botan" in item.window_text().lower():
                        item.click_input()
                        self.log("Kullanıcı seçildi: botan", "success")
                        time.sleep(0.15)
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
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.05)
            sifre.type_keys(MEDULA_SIFRE, with_spaces=True)
            self.log("Şifre girildi", "info")
            time.sleep(0.1)
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

    KEEPALIVE_ESIK = 90  # Saniye - bu süre boyunca Medula'ya tıklanmamışsa keepalive tetiklenir
    AKTIVITE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medula_aktivite.tmp")

    def _son_aktivite_zamani(self):
        """Son Medula aktivite zamanını oku.
        Hem kendi _son_aktivite değişkenine hem de subprocess'in yazdığı dosyaya bakar.
        En yeni olanı döndürür."""
        en_yeni = self._son_aktivite

        # Subprocess'in yazdığı aktivite dosyasını oku
        try:
            if os.path.exists(self.AKTIVITE_FILE):
                with open(self.AKTIVITE_FILE, "r") as f:
                    dosya_zamani = float(f.read().strip())
                    if dosya_zamani > en_yeni:
                        en_yeni = dosya_zamani
        except:
            pass

        return en_yeni

    def aktivite_bildir(self):
        """Medula'ya tıklama yapıldığında çağrılır - keepalive zamanlayıcısını sıfırlar"""
        self._son_aktivite = time.time()
        # Dosyaya da yaz (subprocess de okuyabilsin)
        try:
            with open(self.AKTIVITE_FILE, "w") as f:
                f.write(str(self._son_aktivite))
        except:
            pass

    def keepalive_baslat(self):
        """
        Oturum canlı tutma - DEVRE DIŞI BIRAKILDI.
        Giriş butonuna otomatik basma, aktif tarama akışını bozuyordu.
        """
        logger.info("Keepalive devre dışı - otomatik giriş yapılmayacak")
        return

        if self._keepalive_aktif:
            return

        self._keepalive_aktif = True
        self._son_aktivite = time.time()

        def keepalive_loop():
            while self._keepalive_aktif and self.bagli:
                try:
                    time.sleep(10)  # Her 10 saniyede kontrol et
                    if not self._keepalive_aktif or not self.bagli:
                        break

                    if not self.medula_hwnd or not self.main_window:
                        continue

                    # Son aktiviteden bu yana geçen süre
                    son_zaman = self._son_aktivite_zamani()
                    gecen = time.time() - son_zaman
                    if gecen < self.KEEPALIVE_ESIK:
                        continue

                    # 90 saniye geçti, oturum kontrol et
                    logger.info(f"Keepalive: {gecen:.0f}sn aktivite yok, oturum kontrol ediliyor")

                    try:
                        if not self.oturum_aktif_mi():
                            logger.info("Keepalive: Oturum düşmüş, Giriş butonuna basılıyor")
                            for elem in self.main_window.descendants(control_type="Button"):
                                try:
                                    if elem.element_info.automation_id == "btnMedulayaGirisYap":
                                        elem.click_input()
                                        logger.info("Keepalive: Giriş butonu tıklandı")
                                        break
                                except:
                                    pass
                        else:
                            logger.debug("Keepalive: Oturum hala aktif")
                    except Exception:
                        pass

                    # Aktivite zamanını güncelle (tekrar 90sn beklesin)
                    self._son_aktivite = time.time()

                except Exception as e:
                    logger.debug(f"Keepalive hatası: {e}")

        self._keepalive_thread = threading.Thread(target=keepalive_loop, daemon=True)
        self._keepalive_thread.start()
        self.log("Oturum canlı tutma başlatıldı (90sn inaktivite eşiği)", "info")

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

        Sekme tespiti: Tüm sekme adları ("A","B","C Sıralı","C Kan","GKKKOY","Yurtdışı")
        aynı y koordinatında DataItem olarak bulunur. Önce "C Sıralı" referans sekmesini
        bulup aynı y'deki hedef sekmeyi tıklar (tek harfli "A" gibi sekmelerde
        yanlış elemente tıklamayı önler).
        """
        if not self.bagli:
            return False

        grup_bilgi = next((g for g in GRUP_TANIMLARI if g["kod"] == grup_kodu), None)
        if not grup_bilgi:
            self.log(f"Bilinmeyen grup: {grup_kodu}", "error")
            return False

        medula_tab = grup_bilgi["medula_tab"]

        try:
            # 1. Referans sekmesini bul - GKKKOY kullan (ASCII, encoding sorunu yok)
            referans_y = None
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    if txt and txt.strip() == "GKKKOY":
                        referans_y = elem.rectangle().top
                        break
                except:
                    pass

            if referans_y is None:
                # Alternatif: "B" dene (tek karakter, encoding sorunu yok)
                for elem in self.main_window.descendants(control_type="DataItem"):
                    try:
                        txt = elem.window_text()
                        if txt and txt.strip() == "B":
                            r = elem.rectangle()
                            # B sekmesi çok belirgin olmayabilir - GKKKOY komşusu olmalı
                            referans_y = r.top
                            break
                    except:
                        pass

            if referans_y is None:
                self.log("Sekme satırı bulunamadı (GKKKOY/B referans yok)", "error")
                return False

            # 2. Hedef sekmeyi bul (aynı y satırında)
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    if not txt:
                        continue
                    stripped = txt.strip()

                    # Hedef sekme mi? (encoding-safe karşılaştırma)
                    eslesme = False
                    if medula_tab == stripped:
                        eslesme = True
                    elif medula_tab in ["C Sıralı", "C Sirali"] and "Sıralı" in stripped:
                        eslesme = True
                    elif medula_tab == "C Kan" and "Kan" in stripped and "C" in stripped:
                        eslesme = True
                    elif medula_tab in ["Yurtdışı", "Yurtdisi"] and ("Yurt" in stripped):
                        eslesme = True

                    if eslesme:
                        r = elem.rectangle()
                        if abs(r.top - referans_y) < 5:
                            elem.click_input()
                            self.log(f"'{medula_tab}' sekmesine tıklandı", "success")
                            # Sayfa yüklenmesi için bekle
                            time.sleep(3)
                            return True
                except:
                    pass

            self.log(f"'{medula_tab}' sekmesi bulunamadı (referans_y={referans_y})", "error")
            return False
        except Exception as e:
            self.log(f"Sekme tıklama hatası: {e}", "error")
            return False

    def sorgula(self):
        """Sorgula butonuna tıkla ve reçete listesinin yüklenmesini bekle"""
        if not self.bagli:
            return False

        basarili = self._element_bul_ve_tikla(
            MEDULA_IDS["sorgula_butonu"],
            "Sorgula butonuna tıklandı"
        )
        if basarili:
            # Reçete listesinin yüklenmesini bekle (3L ile başlayan DataItem görünene kadar)
            for bekle in range(10):
                time.sleep(1)
                for elem in self.main_window.descendants(control_type="DataItem"):
                    try:
                        txt = elem.window_text()
                        if txt and len(txt.strip()) == 7 and txt.strip()[0].isdigit() and txt.strip().isalnum():
                            self.log("Reçete listesi yüklendi", "info")
                            time.sleep(1)
                            return True
                    except:
                        pass
            # Timeout - reçete bulunamadı ama sayfa yüklendi
            time.sleep(2)
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
        Reçete no formatı: 3LE + 4 alfanümerik = 7 karakter (ör: 3LEO9QB)
        Returns: list[str] - reçete numaraları
        """
        if not self.bagli:
            return []

        receteler = []
        try:
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    if not txt:
                        continue
                    txt = txt.strip()
                    # Reçete numaraları: 3L ile başlar + 5 alfanümerik = 7 karakter
                    if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                        if txt not in receteler:  # Tekrar engelle
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

            # Reçete No: 7 karakter alfanümerik (3M6WLIF, 3LExxxx vb.)
            for txt, y in texts:
                if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                    bilgiler["recete_no"] = txt
                elif "Sigortalı" in txt or txt.startswith("4"):
                    bilgiler["kapsam"] = txt
                elif "Grubu" in txt:
                    bilgiler["fatura_turu"] = txt
                elif "Sonlandırıldı" in txt:
                    bilgiler["karekod_durumu"] = txt

            # e-Reçete No (kısa format, reçete no'dan farklı)
            for txt, y in texts:
                if len(txt) <= 4 and txt.isalnum() and txt[0].isdigit():
                    bilgiler["e_recete_no"] = txt

        except Exception as e:
            self.log(f"Reçete bilgileri okuma hatası: {e}", "error")

        return bilgiler

    def ilac_tablosu_oku(self):
        """
        Açık reçetedeki ilaç tablosunu AutomationID bazlı oku.

        İlaç tablosu yapısı (keşfedildi 2026-03-28):
        AutomationID deseni: f:tbl1:{row}:xxx
        - f:tbl1:{row}:box32  → Satır container (Table)
        - f:tbl1:{row}:t2     → Adet (Edit)
        - f:tbl1:{row}:t5     → Periyot sayısı (Edit)
        - f:tbl1:{row}:m1     → Periyot birimi (ComboBox: 3=Günde,4=Haftada,5=Ayda)
        - f:tbl1:{row}:t3     → Çarpan (Edit)
        - f:tbl1:{row}:t4     → Doz (Edit, "1,0" formatı)
        - İlaç adı: DataItem (row container altında, uzun text)
        - Stk/Raf + Etkin madde: Doz satırı altında DataItem ("SGKFNL-SALBUTAMOL")
        - Tutar, Fark, Rapor, Verilebileceği, Msj: aynı row'da DataItem

        Returns:
            list[dict]: Her ilaç için bilgi sözlüğü
        """
        ilaclar = []

        try:
            # Kaç satır var? f:tbl1:{row}:box32 sayarak bul
            max_row = -1
            for elem in self.main_window.descendants():
                try:
                    aid = elem.element_info.automation_id
                    if aid and aid.startswith("f:tbl1:") and ":box32" in aid:
                        # f:tbl1:0:box32 → row=0
                        parts = aid.split(":")
                        row = int(parts[2])
                        if row > max_row:
                            max_row = row
                except:
                    pass

            if max_row < 0:
                return ilaclar

            self.log(f"İlaç tablosu: {max_row + 1} satır bulundu", "info")

            # Her element'in automation_id'sini ve text'ini topla
            elem_map = {}  # aid -> text
            for elem in self.main_window.descendants():
                try:
                    aid = elem.element_info.automation_id
                    if aid and "tbl1" in aid:
                        txt = elem.window_text()
                        if txt and txt.strip():
                            elem_map[aid] = txt.strip()
                except:
                    pass

            # Ayrıca DataItem'lardan ilaç adı, tutar, fark vb. oku
            # Her row için DataItem'ları topla
            all_data_items = []
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    aid = elem.element_info.automation_id or ""
                    r = elem.rectangle()
                    if txt and txt.strip():
                        all_data_items.append({
                            "txt": txt.strip(),
                            "aid": aid,
                            "y": r.top,
                            "x": r.left,
                        })
                except:
                    pass

            # Her satırı işle
            for row in range(max_row + 1):
                prefix = f"f:tbl1:{row}:"
                ilac = {
                    "satir": row,
                    "ilac_adi": "",
                    "etkin_madde": "",
                    "sgk_kodu": "",
                    "stk_raf": "",
                    "tutar": "",
                    "fark": "",
                    "rapor_kodu": "",
                    "verilebilecegi": "",
                    "msj": "",
                    "doz": "",
                    "adet": "",
                    "carpan": "",
                    "periyot": "",
                }

                # Edit alanlarını oku (doz bilgileri)
                ilac["adet"] = elem_map.get(f"{prefix}t2", "")
                ilac["periyot"] = elem_map.get(f"{prefix}t5", "")
                ilac["carpan"] = elem_map.get(f"{prefix}t3", "")
                doz_val = elem_map.get(f"{prefix}t4", "")
                if doz_val:
                    ilac["doz"] = doz_val

                # box32 konteynerinin y pozisyonunu bul (satır bazlı gruplama için)
                box_y = None
                for elem in self.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == f"{prefix}box32":
                            box_y = elem.rectangle().top
                            break
                    except:
                        pass

                if box_y is None:
                    continue

                # Bu satırdaki DataItem'ları bul (box_y ile ±40 piksel aralığında)
                row_items = [d for d in all_data_items
                             if abs(d["y"] - box_y) < 40]
                row_items.sort(key=lambda d: d["x"])

                for item in row_items:
                    txt = item["txt"]

                    # Hata/uyarı mesajlarını atla (ilaç adı değil)
                    if any(k in txt.upper() for k in
                           ["VERİLEMEZ", "KONTROL", "UZMAN", "UYUMLU ICD",
                            "DEĞER TEMİZLE", "İNCELEMEYE"]):
                        continue

                    # İlaç adı: uzun text, ilaç formatı veya en uzun text
                    ilac_aday = (
                        len(txt) > 10 and any(k in txt.upper() for k in
                            ["MG", "ML", "TABLET", "KAPSUL", "KAPSÜL", "DOZ",
                             "INH", "GARGARA", "ŞURUP", "DAMLA", "AMPUL",
                             "FLAKON", "KREM", "JEL", "POMAD", "ENJEKTÖR",
                             "ŞASE", "SURUP", "SPRAY", "FITIL", "SOLÜSYON",
                             "SÜSPANSIYON", "ŞIRINGAS", "KALEM", "PATCH",
                             "TOZU", "LOZANJ", "SACHET", "GRANÜL", "MERHEM"])
                    )
                    if ilac_aday:
                        ilac["ilac_adi"] = txt
                    # İlaç adı bulunamadıysa, satırdaki en uzun text'i kullan
                    elif not ilac["ilac_adi"] and len(txt) > 15 and not txt.replace(",", "").replace(".", "").replace(" ", "").isdigit():
                        ilac["_uzun_aday"] = txt
                    # Msj: var/yok
                    elif txt.lower() in ["var", "yok"]:
                        ilac["msj"] = txt.lower()
                    # Verilebileceği: tarih formatı
                    elif "/" in txt and len(txt) == 10 and txt[2] == "/":
                        ilac["verilebilecegi"] = txt
                    # Rapor kodu: XX.XX formatı
                    elif "." in txt and len(txt) <= 8 and txt[0].isdigit():
                        ilac["rapor_kodu"] = txt
                    # Tutar/Fark: sayısal değer (virgüllü)
                    elif txt.replace(",", "").replace(".", "").replace(" ", "").isdigit():
                        if not ilac["tutar"]:
                            ilac["tutar"] = txt
                        elif not ilac["fark"]:
                            ilac["fark"] = txt
                    # Stk/Raf: satır no + depo kodu
                    elif "\n" in txt or ("(" in txt and ")" in txt and len(txt) < 15):
                        ilac["stk_raf"] = txt.replace("\n", " ")

                # Doz satırından etkin madde oku (row+1 piksel altında)
                doz_items = [d for d in all_data_items
                             if d["y"] > box_y + 30 and d["y"] < box_y + 70]
                for item in doz_items:
                    txt = item["txt"]
                    # Doz string: "1 Günde 4 x 2,00 - Adet"
                    if "Günde" in txt or "Haftada" in txt or "Ayda" in txt:
                        ilac["doz"] = txt
                    # Etkin madde: "SGKFNL-SALBUTAMOL" veya "SGKFK3-PIOGLITAZON HCL"
                    elif txt.startswith("SGK") and "-" in txt:
                        parts = txt.split("-", 1)
                        ilac["sgk_kodu"] = parts[0].strip()
                        ilac["etkin_madde"] = parts[1].strip() if len(parts) > 1 else ""

                # Uyarı mesajları (daha altta)
                uyari_items = [d for d in all_data_items
                               if d["y"] > box_y + 60 and d["y"] < box_y + 100]
                for item in uyari_items:
                    txt = item["txt"]
                    if "VERİLEMEZ" in txt or "KONTROL" in txt or "UZMAN" in txt:
                        if "uyari" not in ilac:
                            ilac["uyari"] = []
                        ilac["uyari"].append(txt)

                # İlaç adı bulunamadıysa uzun aday'ı kullan
                if not ilac["ilac_adi"] and ilac.get("_uzun_aday"):
                    ilac["ilac_adi"] = ilac["_uzun_aday"]
                ilac.pop("_uzun_aday", None)

                if ilac["ilac_adi"]:
                    ilaclar.append(ilac)

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

        AutomationID'ler (keşfedildi 2026-03-07 / güncellendi 2026-03-28):
        - Checkbox: f:tbl1:{row}:checkbox7
        - İlaç Bilgi butonu: f:buttonIlacBilgiGorme
        - Etkin madde: form1:text35
        - SGK kodu: form1:text2
        - Mesaj başlığı: form1:tableExIlacMesajListesi:{idx}:text19
        - Mesaj metni: form1:textarea1
        - Kapat butonu: form1:buttonKapat

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
            # 1. Checkbox seç (AutomationID bazlı)
            cb_id = f"f:tbl1:{satir_index}:checkbox7"
            self._element_bul_ve_tikla(cb_id)
            time.sleep(0.3)

            # 2. İlaç Bilgi butonuna tıkla
            self._element_bul_ve_tikla("f:buttonIlacBilgiGorme")
            time.sleep(3)

            # 3. Sayfanın yüklenmesini bekle (form1:buttonKapat görünene kadar)
            for bekle in range(10):
                for elem in self.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "form1:buttonKapat":
                            break
                    except:
                        pass
                else:
                    time.sleep(1)
                    continue
                break

            # 4. AutomationID bazlı bilgi oku
            for elem in self.main_window.descendants():
                try:
                    aid = elem.element_info.automation_id
                    if not aid:
                        continue
                    txt = elem.window_text()
                    if not txt or not txt.strip():
                        continue
                    txt = txt.strip()

                    # Etkin madde
                    if aid == "form1:text35":
                        bilgi["etkin_madde"] = txt
                    # SGK kodu
                    elif aid == "form1:text2":
                        bilgi["sgk_kodu"] = txt
                    # Mesaj başlığı (ilk mesaj)
                    elif "tableExIlacMesajListesi" in aid and "text19" in aid:
                        if not bilgi["mesaj_basligi"]:
                            bilgi["mesaj_basligi"] = txt
                    # Mesaj metni
                    elif aid == "form1:textarea1":
                        bilgi["mesaj_metni"] = txt
                except:
                    pass

            # 5. DataItem'lardan ek bilgileri oku (doz, rapor türü, SUT)
            for elem in self.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    if not txt or not txt.strip():
                        continue
                    txt = txt.strip()

                    if "Günde" in txt and "x" in txt:
                        if not bilgi["ayaktan_maks_doz"]:
                            bilgi["ayaktan_maks_doz"] = txt
                        elif not bilgi["raporlu_maks_doz"]:
                            bilgi["raporlu_maks_doz"] = txt
                    elif "Uzman Hekim Raporu" in txt:
                        bilgi["rapor_turu"] = txt
                    elif "Raporlu" in txt or "Raporsuz" in txt:
                        bilgi["sut_bilgi"] = txt
                except:
                    pass

            self.log(f"İlaç Bilgi okundu: {bilgi.get('etkin_madde', '?')}", "info")

            # 6. Kapat butonu ile geri dön (form1:buttonKapat)
            self._element_bul_ve_tikla("form1:buttonKapat")
            time.sleep(2)

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
                # Reçete no (7 karakter alfanümerik)
                if len(txt) == 7 and txt[0].isdigit() and txt.isalnum() and x < 700:
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
        ekran_w = root.winfo_screenwidth()
        pencere_w = 600
        pencere_h = 950
        pencere_x = ekran_w - pencere_w
        self.root.geometry(f"{pencere_w}x{pencere_h}+{pencere_x}+0")
        self.root.resizable(True, True)
        self.root.configure(bg="#1E3A5F")

        # Log alanı (önce oluştur ki MedulaBaglanti kullanabilsin)
        self.log_text = None

        # Medula bağlantısı
        self.medula = MedulaBaglanti(log_callback=self.log_yaz)

        # Kontrol durumu
        self.kontrol_aktif = False
        self.aktif_grup = None
        self._subprocess_proc = None

        # Escape kısayolu - taramayı durdur
        self.root.bind_all("<Escape>", lambda e: self._taramayi_durdur())

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

        # === RENKLI REÇETE + AY SEÇİMİ SATIRI ===
        ust_ayar_frame = tk.Frame(icerik_frame, bg="#1E3A5F")
        ust_ayar_frame.pack(fill="x", pady=(0, 5))

        # Ay seçimi (önce pack - sağda sabit kalması için)
        self.renkli_recete_dosya = None
        self.renkli_recete_listesi = []

        ay_frame = tk.Frame(ust_ayar_frame, bg="#37474F", bd=1, relief="groove")
        ay_frame.pack(side="right", padx=(5, 0))

        # Renkli Reçete Excel Yükle butonu + hatırla checkbox (kalan alan)
        renkli_frame = tk.Frame(ust_ayar_frame, bg="#37474F", bd=1, relief="groove")
        renkli_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.renkli_btn = tk.Button(
            renkli_frame, text="📋 Renkli Reçete Excel Yükle",
            font=("Segoe UI", 9, "bold"),
            fg="white", bg="#6A1B9A", activebackground="#4A148C",
            bd=0, padx=10, pady=6, cursor="hand2",
            command=self._renkli_recete_yukle
        )
        self.renkli_btn.pack(side="left", padx=3, pady=3)

        self.renkli_durum_label = tk.Label(
            renkli_frame, text="Yüklenmedi",
            font=("Segoe UI", 8), fg="#FF9800", bg="#37474F"
        )
        self.renkli_durum_label.pack(side="left", padx=3)

        # "Hatırla" checkbox
        self.renkli_hatirla_var = tk.BooleanVar(value=True)
        self.renkli_hatirla_cb = tk.Checkbutton(
            renkli_frame, text="✓",
            variable=self.renkli_hatirla_var,
            font=("Segoe UI", 7), fg="#90CAF9", bg="#37474F",
            selectcolor="#263238", activebackground="#37474F",
        )
        self.renkli_hatirla_cb.pack(side="left", padx=0)

        # Otomatik yükleme: kaydedilmiş excel dosyası varsa aç
        self._renkli_excel_hatirla()

        tk.Label(ay_frame, text="Dönem:", font=("Segoe UI", 9),
                 fg="#87CEEB", bg="#37474F").pack(side="left", padx=(5, 2), pady=3)

        from datetime import date
        bugun = date.today()
        aylar = []
        for i in range(6):
            ay = bugun.month - i
            yil = bugun.year
            if ay <= 0:
                ay += 12
                yil -= 1
            ay_adi = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                       "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"][ay]
            aylar.append(f"{yil} {ay_adi}")

        self.donem_var = tk.StringVar(value=aylar[0])
        donem_combo = ttk.Combobox(
            ay_frame, textvariable=self.donem_var,
            values=aylar, state="readonly", width=14,
            font=("Segoe UI", 9)
        )
        donem_combo.pack(side="left", padx=3, pady=3)

        # Ayırıcı
        tk.Frame(icerik_frame, bg="#3D5A80", height=2).pack(fill="x", pady=3)

        # Tümünü Kontrol Et / Durdur toggle butonu
        tumunu_btn = tk.Button(
            icerik_frame,
            text="TÜMÜNÜ KONTROL ET",
            font=("Segoe UI", 14, "bold"),
            fg="white", bg="#00695C", activebackground="#004D40",
            bd=0, padx=20, pady=12, cursor="hand2",
            command=self._tumunu_toggle
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

        rapor_btn = tk.Button(
            secenek_frame, text="Raporu Göster",
            font=("Segoe UI", 9, "bold"), fg="white", bg="#1565C0",
            activebackground="#0D47A1", bd=0, padx=10, pady=3,
            command=self._rapor_tablosu_goster
        )
        rapor_btn.pack(side="right", padx=(0, 5))

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

        # Tag'ler - kontrol sonuçlarına göre renkler
        self.log_text.tag_configure("info", foreground="#87CEEB")           # Nötr - açık mavi
        self.log_text.tag_configure("success", foreground="#0D2137", background="#A5D6A7")  # Uygun - yeşil arka plan
        self.log_text.tag_configure("warning", foreground="#0D2137", background="#FFE082")  # Şüpheli/bilinemeyen - sarı
        self.log_text.tag_configure("error", foreground="#FFFFFF", background="#E53935")    # Uygunsuz - kırmızı
        self.log_text.tag_configure("sorun", foreground="#FFFFFF", background="#D84315")    # Sorun - koyu turuncu
        self.log_text.tag_configure("header", foreground="#FFFFFF", font=("Consolas", 10, "bold"))
        self.log_text.tag_configure("neutral", foreground="#B0BEC5")        # Nötr - gri (GEÇ satırları)

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
            command=lambda k=kod: self._grup_toggle(k)
        )
        btn.pack(side="left")
        self.grup_butonlari[kod] = btn
        # Orijinal rengi sakla
        btn._renk_normal = grup["renk"]
        btn._renk_hover = grup["hover"]
        btn._ad = grup["ad"]

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
        """
        Medula bağlan butonuna tıklandı.
        Her durumda çalışır: açık/kapalı/ölmüş fark etmez.
        Gerekirse taskkill + restart yapar.
        """
        self.log_yaz("Medula'ya bağlanılıyor...", "info")
        self.medula_durum_label.config(text="Durum: İşlem yapılıyor...", fg="#FF9800")
        self.root.update()

        def islem():
            import subprocess

            # 1. Medula penceresi varsa bağlan ve oturum kontrol et
            basarili = self.medula.medula_baglan() if not self.medula.bagli else True
            if self.medula.bagli:
                # Oturum aktif mi?
                if self.medula.oturum_aktif_mi():
                    self.root.after(0, lambda: self.log_yaz("Medula bağlı ve oturum aktif", "success"))
                    self.root.after(0, lambda: self._medula_baglanti_sonuc(True))
                    return

                # Oturum düşmüş - giriş butonu ile yenilemeyi dene
                self.root.after(0, lambda: self.log_yaz("Oturum düşmüş, giriş butonu deneniyor...", "warning"))
                for deneme in range(3):
                    if self.medula.main_window:
                        for elem in self.medula.main_window.descendants():
                            try:
                                if elem.element_info.automation_id == "btnMedulayaGirisYap":
                                    elem.click_input()
                                    break
                            except:
                                pass
                    time.sleep(5)
                    if self.medula.oturum_aktif_mi():
                        self.root.after(0, lambda: self.log_yaz("Oturum yenilendi!", "success"))
                        self.root.after(0, lambda: self._medula_baglanti_sonuc(True))
                        return

                # Giriş butonu da işe yaramadı
                self.root.after(0, lambda: self.log_yaz("Oturum yenilenemedi, Medula kapatılıp yeniden açılıyor...", "warning"))

            # 2. Taskkill - eski pencereyi kapat
            self.medula.keepalive_durdur()
            try:
                subprocess.run(["taskkill", "/F", "/IM", "BotanikMedula.exe"],
                               capture_output=True, text=True, timeout=10)
            except:
                pass
            self.medula.bagli = False
            self.medula.main_window = None
            self.medula.medula_hwnd = None
            time.sleep(3)

            # 3. Yeniden başlat ve giriş yap
            basarili = self.medula._exe_baslat_ve_giris_yap()
            if basarili:
                time.sleep(3)
                # Oturum aktif olana kadar giriş butonu bas
                for _ in range(5):
                    if self.medula.oturum_aktif_mi():
                        self.root.after(0, lambda: self._medula_baglanti_sonuc(True))
                        return
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

            self.root.after(0, lambda: self._medula_baglanti_sonuc(False))

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

    # === RENKLİ REÇETE EXCEL YÜKLEME ===

    def _renkli_recete_yukle(self):
        """Renkli reçete Excel dosyası yükle (Gözat dialog)"""
        from tkinter import filedialog
        dosya = filedialog.askopenfilename(
            title="Renkli Reçete Excel Dosyası Seç",
            filetypes=[("Excel Dosyaları", "*.xlsx *.xls"), ("Tüm Dosyalar", "*.*")],
            initialdir=os.path.expanduser("~/OneDrive/Desktop")
        )
        if dosya:
            self._renkli_excel_isle(dosya)

    def _renkli_excel_isle(self, dosya_yolu):
        """Excel dosyasını oku ve renkli reçete listesini oluştur"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(dosya_yolu, read_only=True)
            ws = wb.active

            self.renkli_recete_listesi = []
            baslik_satiri = True
            for row in ws.iter_rows(values_only=True):
                if baslik_satiri:
                    baslik_satiri = False
                    continue
                if row[0]:
                    recete_no_raw = str(row[0]).strip()
                    # "ZTHPW2PU / 2MBOFVQ" formatı - her iki no'yu da kaydet
                    recete_nolar = [n.strip() for n in recete_no_raw.split("/")]
                    hasta = str(row[1] or "").strip()
                    hekim = str(row[2] or "").strip()
                    tarih = str(row[4] or "").strip()

                    self.renkli_recete_listesi.append({
                        "recete_nolar": recete_nolar,
                        "recete_no_raw": recete_no_raw,
                        "hasta": hasta,
                        "hekim": hekim,
                        "tarih": tarih,
                    })
            wb.close()

            self.renkli_recete_dosya = dosya_yolu
            sayi = len(self.renkli_recete_listesi)
            dosya_adi = os.path.basename(dosya_yolu)
            self.renkli_durum_label.config(
                text=f"✓ {dosya_adi} ({sayi} reçete)", fg="#4CAF50"
            )
            self.renkli_btn.config(bg="#4A148C")
            self.log_yaz(f"Renkli reçete listesi yüklendi: {sayi} reçete ({dosya_adi})", "success")

            # Dosya yolunu hatırla (checkbox işaretliyse JSON'a kaydet)
            if self.renkli_hatirla_var.get():
                self._renkli_excel_kaydet(dosya_yolu)

        except Exception as e:
            self.log_yaz(f"Renkli reçete yükleme hatası: {e}", "error")
            self.renkli_durum_label.config(text="Yükleme hatası!", fg="#F44336")

    def _renkli_excel_kaydet(self, dosya_yolu):
        """Renkli reçete excel dosya yolunu JSON'a kaydet"""
        try:
            durum = {}
            if os.path.exists(DURUM_DOSYASI):
                with open(DURUM_DOSYASI, "r", encoding="utf-8") as f:
                    durum = json.load(f)
            durum["_renkli_excel_dosya"] = dosya_yolu
            with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(durum, f, indent=2, ensure_ascii=False)
        except:
            pass

    def _renkli_excel_hatirla(self):
        """Kaydedilmiş renkli reçete excel dosyasını otomatik yükle"""
        try:
            if os.path.exists(DURUM_DOSYASI):
                with open(DURUM_DOSYASI, "r", encoding="utf-8") as f:
                    durum = json.load(f)
                dosya = durum.get("_renkli_excel_dosya", "")
                if dosya and os.path.exists(dosya):
                    self._renkli_excel_isle(dosya)
        except:
            pass

    def renkli_recete_kontrol(self, recete_no):
        """
        Bir reçete no'sunun renkli reçete listesinde olup olmadığını kontrol et.
        Returns: (bulundu: bool, kayit: dict or None)
        """
        if not self.renkli_recete_listesi:
            return False, None

        for kayit in self.renkli_recete_listesi:
            for no in kayit["recete_nolar"]:
                if no == recete_no:
                    return True, kayit
        return False, None

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

        self.aktif_grup = "TUMU"
        self.tumunu_btn.config(text="DURDUR (Esc)", bg="#B71C1C", activebackground="#7F0000")
        for btn in self.grup_butonlari.values():
            btn.config(state="disabled")

        def kontrol_thread():
            self.kontrol_aktif = True
            try:
                for grup in GRUP_TANIMLARI:
                    if not self.kontrol_aktif:
                        break
                    self._grup_kontrol_islemi(grup["kod"])
            finally:
                self.kontrol_aktif = False
                self.aktif_grup = None
                self.root.after(0, self._butonlari_normal_yap)
                self.root.after(0, lambda: self.log_yaz("Tüm kontroller tamamlandı", "header"))

        threading.Thread(target=kontrol_thread, daemon=True).start()

    def _medula_hazirla(self):
        """Medula bağlantısını kontrol et, yoksa/düşmüşse yeniden bağlan.
        Worker thread'den çağrılır. GUI güncellemeleri root.after ile yapılır.
        descendants() taraması yapmaz - SPAN popup sorununu önler.
        Returns: True=hazır, False=bağlanılamadı
        """
        import subprocess as sp
        import win32gui

        def _log(msg, tag="info"):
            self.root.after(0, lambda m=msg, t=tag: self.log_yaz(m, t))

        def _pencere_bul(filtre):
            """win32gui ile pencere ara. filtre(title)->bool"""
            sonuc = [None]
            def cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if t and filtre(t):
                        sonuc[0] = hwnd
            win32gui.EnumWindows(cb, None)
            return sonuc[0]

        def _medula_hwnd():
            return _pencere_bul(lambda t: "MEDULA" in t)

        def _giris_hwnd():
            return _pencere_bul(lambda t: "BotanikEOS" in t and "(T)" in t and "MEDULA" not in t)

        def _medula_web_oturum_bekle():
            """MEDULA penceresi açıldıktan sonra web oturumunun aktif olmasını bekle.
            recete_tarama.py subprocess zaten kendi oturum kontrolünü yapıyor,
            bu yüzden burada sadece pencere var mı kontrol yeterli."""
            self.medula.medula_baglan()
            if self.medula.bagli:
                self.root.after(0, lambda: self._medula_baglanti_sonuc(True))
                return True
            return False

        def _hizli_giris_yap():
            """Giriş penceresine kullanıcı+şifre+enter hızlıca gir.
            Sadece giriş penceresi elementlerine dokunur, MEDULA descendants taramaz."""
            import pyautogui
            pyautogui.FAILSAFE = False
            from pywinauto import Desktop

            hwnd = _giris_hwnd()
            if not hwnd:
                _log("Giriş penceresi bulunamadı!", "error")
                return False

            desktop = Desktop(backend="uia")
            giris = desktop.window(handle=hwnd)
            giris.set_focus()
            time.sleep(0.3)

            # Kullanıcı seç
            try:
                combo = giris.child_window(auto_id="cmbKullanicilar")
                combo.click_input()
                time.sleep(0.3)
                for item in combo.descendants(control_type="ListItem"):
                    if "botan" in item.window_text().lower():
                        item.click_input()
                        break
            except Exception as e:
                _log(f"Kullanıcı seçilemedi: {e}", "error")
                return False

            time.sleep(0.15)

            # Şifre gir
            try:
                sifre = giris.child_window(auto_id="txtSifre")
                sifre.click_input()
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.05)
                sifre.type_keys(MEDULA_SIFRE, with_spaces=True)
            except Exception as e:
                _log(f"Şifre girilemedi: {e}", "error")
                return False

            time.sleep(0.1)

            # Giriş butonuna bas
            try:
                btn = giris.child_window(auto_id="btnGirisYap")
                btn.click_input()
                _log("Giriş butonuna basıldı, MEDULA bekleniyor...", "info")
            except Exception as e:
                _log(f"Giriş butonu tıklanamadı: {e}", "error")
                return False

            # MEDULA penceresi açılana kadar bekle
            for i in range(20):
                time.sleep(1)
                if _medula_hwnd():
                    _log(f"MEDULA açıldı! ({i+1} sn)", "success")
                    return True
                if i == 5:
                    try:
                        giris.child_window(auto_id="btnGirisYap").click_input()
                    except:
                        pass

            _log("MEDULA penceresi açılamadı", "error")
            return False

        # === ANA AKIŞ ===

        # 1. MEDULA penceresi zaten açık mı? → Direkt bağlan, subprocess halleder
        if _medula_hwnd():
            _log("Medula penceresi açık, bağlanılıyor...", "info")
            _medula_web_oturum_bekle()
            _log("Medula bağlı, subprocess'e bırakılıyor", "success")
            return True

        # 2. MEDULA yok - BotanikMedula.exe başlat → giriş → MEDULA bekle
        _log("MEDULA penceresi yok, BotanikMedula.exe başlatılıyor...", "info")
        try:
            sp.Popen([MEDULA_EXE], cwd=os.path.dirname(MEDULA_EXE))
        except Exception as e:
            _log(f"BotanikMedula.exe başlatılamadı: {e}", "error")
            self.root.after(0, lambda: self._medula_baglanti_sonuc(False))
            return False

        # Giriş penceresi (SifreSorForm) bekle
        from pywinauto import Desktop as Dsk
        giris_win = None
        for i in range(20):
            time.sleep(1)
            try:
                dsk = Dsk(backend="uia")
                for w in dsk.windows():
                    try:
                        if w.element_info.automation_id == "SifreSorForm":
                            giris_win = w
                            _log(f"Giriş penceresi açıldı ({i+1} sn)", "info")
                            break
                    except:
                        pass
                if giris_win:
                    break
            except:
                pass

        if giris_win:
            try:
                import pyautogui
                pyautogui.FAILSAFE = False
                giris_win.set_focus()
                time.sleep(0.3)
                combo = giris_win.child_window(auto_id="cmbKullanicilar")
                combo.click_input()
                time.sleep(0.3)
                for item in combo.children():
                    try:
                        if "botan" in item.window_text().lower():
                            item.click_input()
                            _log("Kullanıcı: botan", "info")
                            break
                    except:
                        pass
                time.sleep(0.3)
                sifre = giris_win.child_window(auto_id="txtSifre")
                sifre.click_input()
                time.sleep(0.1)
                sifre.type_keys(MEDULA_SIFRE, with_spaces=True)
                time.sleep(0.1)
                giris_win.child_window(auto_id="btnGirisYap").click_input()
                _log("Giriş yapılıyor...", "info")
            except Exception as e:
                _log(f"Giriş hatası: {e}", "error")

        # MEDULA penceresi bekle
        for i in range(30):
            time.sleep(1)
            if _medula_hwnd():
                _log(f"MEDULA açıldı ({i+1} sn)", "success")
                _medula_web_oturum_bekle()
                return True
            if (i + 1) % 10 == 0:
                _log(f"MEDULA bekleniyor... ({i+1} sn)", "info")

        _log("MEDULA açılamadı!", "error")
        self.root.after(0, lambda: self._medula_baglanti_sonuc(False))
        return False

    def _rapor_tablosu_goster(self):
        """Tarama raporu JSON'ını oku ve yeni pencerede tablo olarak göster"""
        rapor_json = os.path.join(PROJE_DIZINI, "tarama_rapor.json")
        if not os.path.exists(rapor_json):
            self.log_yaz("Henüz rapor yok! Önce bir tarama yapın.", "warning")
            return

        try:
            with open(rapor_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.log_yaz(f"Rapor dosyası okunamadı: {e}", "error")
            return

        satirlar = data.get("satirlar", [])
        grup = data.get("grup", "?")
        tarih = data.get("tarih", "")[:16].replace("T", " ")

        if not satirlar:
            self.log_yaz("Rapor boş!", "warning")
            return

        # Yeni pencere
        rapor_win = tk.Toplevel(self.root)
        rapor_win.title(f"Kontrol Raporu - {grup} Grubu ({tarih})")
        rapor_win.geometry("1200x600")
        rapor_win.configure(bg="#1E3A5F")

        # Üst bilgi
        ust = tk.Frame(rapor_win, bg="#1E3A5F")
        ust.pack(fill="x", padx=5, pady=5)
        tk.Label(ust, text=f"Kontrol Raporu - {grup} Grubu  |  {tarih}  |  {len(satirlar)} satır",
                 font=("Segoe UI", 12, "bold"), fg="white", bg="#1E3A5F").pack(side="left")

        # Excel'e aktar butonu
        def excel_ac():
            masaustu = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
            import glob as g
            dosyalar = sorted(g.glob(os.path.join(masaustu, f"Kontrol_Raporu_{grup}_*.xlsx")))
            if dosyalar:
                os.startfile(dosyalar[-1])
            else:
                self.log_yaz("Excel dosyası bulunamadı!", "warning")

        tk.Button(ust, text="Excel Aç", font=("Segoe UI", 10, "bold"),
                  fg="white", bg="#1565C0", activebackground="#0D47A1",
                  bd=0, padx=10, pady=3, command=excel_ac).pack(side="right")

        # Treeview tablo
        from tkinter import ttk
        sutunlar = ("recete_no", "recete_turu", "ilac_adi", "etkin_madde",
                     "rapor_kodu", "msj", "renkli_kontrol", "rapor_kontrol",
                     "sut_kontrol", "sonuc", "aciklama")
        basliklar = ("Reçete No", "Tür", "İlaç Adı", "Etkin Madde",
                     "Rapor", "Msj", "Renkli", "Rapor K.", "SUT K.", "Sonuç", "Açıklama")
        genislikler = (85, 70, 280, 170, 60, 35, 90, 90, 80, 65, 300)

        style = ttk.Style()
        style.configure("Rapor.Treeview", font=("Segoe UI", 9), rowheight=24)
        style.configure("Rapor.Treeview.Heading", font=("Segoe UI", 9, "bold"))

        tablo_frame = tk.Frame(rapor_win, bg="#1E3A5F")
        tablo_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        tree = ttk.Treeview(tablo_frame, columns=sutunlar, show="headings",
                            style="Rapor.Treeview", selectmode="browse")

        for col, baslik, gen in zip(sutunlar, basliklar, genislikler):
            tree.heading(col, text=baslik)
            tree.column(col, width=gen, minwidth=30)

        # Scrollbar
        yscroll = ttk.Scrollbar(tablo_frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(tablo_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)

        # Tag renkler
        tree.tag_configure("OK", background="#C8E6C9")
        tree.tag_configure("SORUN", background="#FFCDD2", foreground="#B71C1C")
        tree.tag_configure("UYARI", background="#FFF9C4")
        tree.tag_configure("YENİ", background="#B3E5FC")
        tree.tag_configure("recete", background="#E8EAF6", font=("Segoe UI", 9, "bold"))

        # Veri ekle
        onceki_recete = None
        for satir in satirlar:
            recete_no = satir.get("recete_no", "")
            yeni_recete = recete_no != onceki_recete
            onceki_recete = recete_no

            degerler = (
                recete_no if yeni_recete else "",
                satir.get("recete_turu", "") if yeni_recete else "",
                satir.get("ilac_adi", ""),
                satir.get("etkin_madde", ""),
                satir.get("rapor_kodu", ""),
                satir.get("msj", ""),
                satir.get("renkli_kontrol", "-"),
                satir.get("rapor_kontrol", "-"),
                satir.get("sut_kontrol", "-"),
                satir.get("sonuc", ""),
                satir.get("aciklama", ""),
            )

            sonuc = satir.get("sonuc", "")
            tag = sonuc if sonuc in ("OK", "SORUN", "UYARI") else "YENİ" if sonuc == "YENİ" else ""
            tree.insert("", "end", values=degerler, tags=(tag,))

        # Alt bilgi
        sorun_sayisi = sum(1 for s in satirlar if s.get("sonuc") == "SORUN")
        uyari_sayisi = sum(1 for s in satirlar if s.get("sonuc") == "UYARI")
        yeni_sayisi = sum(1 for s in satirlar if s.get("sonuc") == "YENİ")
        ok_sayisi = sum(1 for s in satirlar if s.get("sonuc") == "OK")

        alt = tk.Frame(rapor_win, bg="#1E3A5F")
        alt.pack(fill="x", padx=5, pady=3)
        tk.Label(alt, text=f"OK: {ok_sayisi}", fg="#4CAF50", bg="#1E3A5F",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)
        tk.Label(alt, text=f"Sorun: {sorun_sayisi}", fg="#F44336", bg="#1E3A5F",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)
        tk.Label(alt, text=f"Uyarı: {uyari_sayisi}", fg="#FF9800", bg="#1E3A5F",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)
        tk.Label(alt, text=f"Yeni: {yeni_sayisi}", fg="#03A9F4", bg="#1E3A5F",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)

    def _pencereleri_konumlandir(self):
        """Tarama başladığında pencereleri konumlandır:
        Medula sol %60, Botanik Takip sağ %40 - yan yana, tam yükseklik"""
        try:
            import win32gui, win32con

            # Ekran boyutu (taskbar hariç çalışma alanı)
            import ctypes
            user32 = ctypes.windll.user32

            # Çalışma alanı (taskbar hariç)
            from ctypes import wintypes
            rect = wintypes.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
            ekran_w = rect.right - rect.left
            ekran_h = rect.bottom - rect.top

            # Medula: sol %60
            medula_w = int(ekran_w * 0.60)
            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "MEDULA" in title:
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.MoveWindow(hwnd, 0, 0, medula_w, ekran_h, True)
            win32gui.EnumWindows(enum_cb, None)

            # Botanik Takip: sağ %40, yükseklik 100px kısa (görev çubuğu üstünde kalması için)
            bt_w = ekran_w - medula_w
            bt_x = medula_w
            bt_h = ekran_h - 50
            self.root.after(0, lambda: self.root.geometry(
                f"{bt_w}x{bt_h}+{bt_x}+0"))

        except Exception as e:
            logger.debug(f"Pencere konumlandırma hatası: {e}")

    def _taramayi_durdur(self):
        """Taramayı durdur - STOP dosyası oluştur ve subprocess'i terminate et"""
        if not self.kontrol_aktif:
            return

        self.log_yaz("TARAMA DURDURULUYOR...", "warning")

        # 1. STOP dosyası oluştur (subprocess kendi döngüsünde kontrol eder)
        try:
            stop_path = os.path.join(PROJE_DIZINI, "tarama_stop.flag")
            with open(stop_path, "w") as f:
                f.write("stop")
        except:
            pass

        # 2. Subprocess'i terminate et
        if self._subprocess_proc:
            try:
                self._subprocess_proc.terminate()
                self.log_yaz("Subprocess durduruldu", "warning")
            except:
                pass
            self._subprocess_proc = None

        self.kontrol_aktif = False
        self._butonlari_normal_yap()

    def _butonlari_durdur_yap(self, aktif_kod=None):
        """Aktif grubun butonunu DURDUR haline getir, diğerlerini devre dışı bırak"""
        for kod, btn in self.grup_butonlari.items():
            if kod == aktif_kod:
                btn.config(text="  DURDUR (Esc)", bg="#B71C1C", activebackground="#7F0000")
            else:
                btn.config(state="disabled")
        self.tumunu_btn.config(state="disabled")

    def _butonlari_normal_yap(self):
        """Tüm butonları normal haline döndür"""
        for kod, btn in self.grup_butonlari.items():
            btn.config(text=f"  {btn._ad}", bg=btn._renk_normal,
                      activebackground=btn._renk_hover, state="normal")
        self.tumunu_btn.config(text="TÜMÜNÜ KONTROL ET", bg="#00695C",
                              activebackground="#004D40", state="normal")

    def _grup_toggle(self, grup_kodu):
        """Grup butonu toggle - basınca başlat, tekrar basınca durdur"""
        if self.kontrol_aktif and self.aktif_grup == grup_kodu:
            self._taramayi_durdur()
        elif not self.kontrol_aktif:
            self._grup_kontrol_baslat(grup_kodu)

    def _tumunu_toggle(self):
        """Tümünü Kontrol Et toggle"""
        if self.kontrol_aktif:
            self._taramayi_durdur()
        else:
            self._tumunu_kontrol_et()

    def _grup_kontrol_baslat(self, grup_kodu):
        """Belirli bir grubun kontrolünü subprocess ile başlat"""
        if self.kontrol_aktif:
            self.log_yaz("Zaten bir kontrol devam ediyor!", "warning")
            return

        donem_offset = self._donem_offset_hesapla()
        secilen_donem = self.donem_var.get()
        grup_adi = next((g["ad"] for g in GRUP_TANIMLARI if g["kod"] == grup_kodu), grup_kodu)

        self.log_yaz(f"{'━' * 40}", "header")
        self.log_yaz(f"{grup_adi} kontrolü başlatılıyor - {secilen_donem}", "header")

        self.aktif_grup = grup_kodu
        self._butonlari_durdur_yap(grup_kodu)

        def kontrol_thread():
            self.kontrol_aktif = True
            try:
                # Önce Medula hazır mı kontrol et, değilse aç ve bağlan
                self.root.after(0, lambda: self.log_yaz("Medula bağlantısı kontrol ediliyor...", "info"))
                if not self._medula_hazirla():
                    self.root.after(0, lambda: self.log_yaz(
                        "Medula bağlantısı kurulamadı! Kontrol iptal edildi.", "error"))
                    return

                # Pencereleri konumlandır: Medula sol, Botanik Takip sağ
                self._pencereleri_konumlandir()

                # Medula hazır, subprocess başlat
                self.root.after(0, lambda: self.log_yaz(
                    "Subprocess ile recete_tarama.py çalıştırılıyor...", "info"))

                import subprocess as sp
                tarama_script = os.path.join(PROJE_DIZINI, "recete_tarama.py")
                proc = sp.Popen(
                    ["python", "-u", tarama_script, grup_kodu, str(donem_offset),
                     "--bastan" if self.bastan_var.get() else "--devam"],
                    stdout=sp.PIPE, stderr=sp.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    cwd=PROJE_DIZINI
                )
                self._subprocess_proc = proc

                # stdout'u satır satır oku ve GUI log'a + terminale yaz
                for line in proc.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    # Terminale yaz
                    print(line, flush=True)
                    # Son reçete bilgisini parse et (label güncelleme)
                    if "[SON_RECETE]" in line:
                        try:
                            parts = line.split("[SON_RECETE]")[1].strip().split(":")
                            if len(parts) == 2:
                                grp, rno = parts[0].strip(), parts[1].strip()
                                self.root.after(0, lambda g=grp, r=rno: self.grup_durumu_guncelle(g, r))
                        except:
                            pass
                        continue  # Bu satırı loga yazma

                    # Log seviyesini parse et - kontrol sonuçlarına göre renk
                    tag = "info"
                    if "[SORUN]" in line or "Doz aşımı" in line or "UYGUNSUZ" in line or "RAPORSUZ yazılmış" in line:
                        tag = "error"       # Kırmızı - uygunsuz
                    elif "[HATA!]" in line:
                        tag = "sorun"       # Koyu turuncu - sistem hatası
                    elif "[????]" in line or "KontrolEdilemedi" in line or "KONTROLEDİLEMEDİ" in line:
                        tag = "warning"     # Sarı - bilinemeyen
                    elif "[  OK  ]" in line or "[  OK ]" in line or "UYGUN" in line:
                        tag = "success"     # Yeşil - uygun
                    elif "[GEÇ ]" in line:
                        tag = "neutral"     # Gri - nötr (raporsuz mesajsız)
                    elif "[=====]" in line:
                        tag = "header"
                    self.root.after(0, lambda l=line, t=tag: self.log_yaz(l, t))

                proc.wait()
                self.root.after(0, lambda: self.log_yaz(
                    f"Subprocess tamamlandı (exit: {proc.returncode})",
                    "success" if proc.returncode == 0 else "error"))
            except Exception as e:
                self.root.after(0, lambda e=e: self.log_yaz(f"Subprocess hatası: {e}", "error"))
            finally:
                self.kontrol_aktif = False
                self._subprocess_proc = None
                self.aktif_grup = None
                self.root.after(0, self._butonlari_normal_yap)

        threading.Thread(target=kontrol_thread, daemon=True).start()

    def _donem_offset_hesapla(self):
        """GUI'deki dönem seçimine göre Medula dropdown offset hesapla"""
        from datetime import date
        secilen = self.donem_var.get()  # "2026 Mart" gibi
        bugun = date.today()
        ay_isimleri = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                       "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        # Seçilen ayı parse et
        parts = secilen.split()
        if len(parts) == 2:
            secilen_yil = int(parts[0])
            secilen_ay = ay_isimleri.index(parts[1]) if parts[1] in ay_isimleri else bugun.month
        else:
            secilen_yil = bugun.year
            secilen_ay = bugun.month
        # Offset = bu ay - seçilen ay (ay farkı)
        offset = (bugun.year * 12 + bugun.month) - (secilen_yil * 12 + secilen_ay)
        return max(0, offset)

    def _grup_kontrol_islemi(self, grup_kodu):
        """
        Bir grubun tam kontrol akışı (thread içinde çalışır).
        Yeni akış:
        1. Medula bağlan + oturum kontrol
        2. Reçete Listesi → Dönem seç → Sorgula → Grup sekmesi
        3. İlk reçeteye tıkla
        4. Her reçete için:
           a. Reçete türü kontrol (beyaz/kırmızı/yeşil/mor)
           b. Renkli ise → Excel listesinde var mı kontrol
           c. İlaç satırlarını oku (DataItem'lardan)
           d. Her ilaç için algoritmik SUT kontrol
           e. Rapor tablosuna yaz
           f. Sonraki Reçete (invoke ile)
        5. Reçete bulunamadı gelince dur → Excel rapor oluştur
        """
        import pyautogui
        pyautogui.FAILSAFE = False
        from recete_kontrol_motoru import ReceteKontrolMotoru, KontrolSonuc

        grup_adi = next((g["ad"] for g in GRUP_TANIMLARI if g["kod"] == grup_kodu), grup_kodu)
        donem_offset = self._donem_offset_hesapla()
        secilen_donem = self.donem_var.get()

        def log(msg, tag="info"):
            self.root.after(0, lambda m=msg, t=tag: self.log_yaz(m, t))

        log(f"{'━' * 40}", "header")
        log(f"{grup_adi} kontrolü başlatılıyor - {secilen_donem}", "header")
        log(f"{'━' * 40}", "header")

        # === 1. MEDULA BAĞLANTI ===
        # Bağlı değilse bağlan
        if not self.medula.bagli:
            log("Medula'ya bağlanılıyor...", "info")
            self.medula.medula_baglan()

        if not self.medula.bagli:
            log("Medula penceresi bulunamadı, açılıyor...", "warning")
            self.medula.medula_ac_ve_baglan()

        if not self.medula.bagli or not self.medula.main_window:
            log("Medula'ya bağlanılamadı!", "error")
            self.root.after(0, lambda: self._medula_baglanti_sonuc(False))
            return

        # Oturum kontrol - thread-safe try/except
        oturum_ok = False
        try:
            oturum_ok = self.medula.oturum_aktif_mi()
        except Exception:
            # Access violation veya benzeri hata - devam et, invoke denenecek
            oturum_ok = True  # Aktif kabul et, sorun olursa invoke hata verir

        if not oturum_ok:
            log("Oturum düşmüş, yenileniyor...", "warning")
            for _ in range(5):
                try:
                    for elem in self.medula.main_window.descendants():
                        try:
                            if elem.element_info.automation_id == "btnMedulayaGirisYap":
                                elem.click_input()
                                break
                        except:
                            pass
                except Exception:
                    pass
                time.sleep(4)
                try:
                    if self.medula.oturum_aktif_mi():
                        oturum_ok = True
                        break
                except Exception:
                    oturum_ok = True  # Hata durumunda devam et
                    break

        if not oturum_ok:
            log("Medula oturumu başlatılamadı! Önce MEDULA Bağlan butonunu kullanın.", "error")
            return

        self.root.after(0, lambda: self._medula_baglanti_sonuc(True))
        log("Medula bağlı ve oturum aktif", "success")

        # === 2. REÇETE LİSTESİ → DÖNEM → FATURA TÜRÜ → SORGULA ===
        # NOT: Web elementleri y=0,x=0 olabilir, bu yüzden:
        #   - Menü linkleri → invoke() ile
        #   - Combobox'lar → click_input() + keyboard ile
        #   - Butonlar → invoke() ile

        log("Reçete Listesi sayfasına gidiliyor...", "info")
        for elem in self.medula.main_window.descendants():
            try:
                if elem.element_info.automation_id == "form1:menuHtmlCommandExButton31":
                    elem.invoke()
                    log("Reçete Listesi menüsü açıldı", "success")
                    break
            except:
                pass

        # Sorgula butonunu bekle (sayfa yüklendi mi?) - 30 saniye timeout
        sorgula_var = False
        for bekle in range(30):
            time.sleep(1)
            try:
                for elem in self.medula.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "form1:buttonSonlandirilmamisReceteler":
                            sorgula_var = True
                            break
                    except:
                        pass
            except Exception:
                pass  # access violation durumunda devam
            if sorgula_var:
                break

        if not sorgula_var:
            # 2. deneme - invoke tekrar
            log("Sayfa yüklenemedi, tekrar deneniyor...", "warning")
            for elem in self.medula.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "form1:menuHtmlCommandExButton31":
                        elem.invoke()
                        break
                except:
                    pass
            time.sleep(10)
            try:
                for elem in self.medula.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "form1:buttonSonlandirilmamisReceteler":
                            sorgula_var = True
                            break
                    except:
                        pass
            except Exception:
                pass

        if not sorgula_var:
            log("Reçete Listesi sayfası yüklenemedi!", "error")
            return

        # ADIM 1: Dönem seçimi (form1:menu2)
        # click_input ile combobox'a odaklan, down ile eski aya git
        if donem_offset > 0:
            log(f"Dönem: {secilen_donem} seçiliyor...", "info")
            for elem in self.medula.main_window.descendants():
                try:
                    if elem.element_info.automation_id == "form1:menu2":
                        elem.click_input()
                        time.sleep(0.5)
                        for _ in range(donem_offset):
                            pyautogui.press("down")
                            time.sleep(0.15)
                        pyautogui.press("enter")
                        log(f"Dönem seçildi: {secilen_donem}", "success")
                        break
                except:
                    pass
            time.sleep(1)

        # ADIM 2: Fatura Türü combobox (form1:menu1)
        # click_input → 20x up (en başa) → N down → enter
        grup_combo_index = {
            "A": 1,    # A Grubu
            "B": 4,    # B Grubu
            "C": 7,    # C Grubu Sıralı Dağıtım
            "CK": 10,  # C Grubu Kan Ürünü
            "GK": 16,  # Yeşil Kart Normal
        }
        combo_idx = grup_combo_index.get(grup_kodu, 1)

        log(f"Fatura Türü: {grup_adi} seçiliyor...", "info")
        for elem in self.medula.main_window.descendants():
            try:
                if elem.element_info.automation_id == "form1:menu1":
                    elem.click_input()
                    time.sleep(0.5)
                    # En başa git (20x up yeterli)
                    for _ in range(20):
                        pyautogui.press("up")
                        time.sleep(0.03)
                    time.sleep(0.2)
                    # İstenen gruba git
                    for _ in range(combo_idx):
                        pyautogui.press("down")
                        time.sleep(0.1)
                    pyautogui.press("enter")
                    log(f"Fatura Türü seçildi: {grup_adi}", "success")
                    break
            except:
                pass
        time.sleep(1)

        # ADIM 3: Sorgula (invoke ile)
        log("Sorgula butonuna basılıyor...", "info")
        for elem in self.medula.main_window.descendants():
            try:
                if elem.element_info.automation_id == "form1:buttonSonlandirilmamisReceteler":
                    elem.invoke()
                    log("Sorgula tıklandı", "success")
                    break
            except:
                pass
        time.sleep(8)

        # === 3. İLK REÇETEYE TIKLA ===
        ilk_recete = None
        try:
            for elem in self.medula.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    if txt:
                        txt = txt.strip()
                        if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                            elem.click_input()
                            ilk_recete = txt
                            break
                except:
                    pass
        except Exception:
            pass

        if not ilk_recete:
            log(f"{grup_adi}: Reçete bulunamadı!", "warning")
            return

        log(f"İlk reçete açılıyor: {ilk_recete}", "info")

        # İlaç tablosu yüklenene kadar bekle (ilaç formu anahtar kelimesi görünene kadar)
        for bekle in range(15):
            time.sleep(1)
            try:
                for elem in self.medula.main_window.descendants(control_type="DataItem"):
                    try:
                        txt = elem.window_text()
                        if txt and any(k in txt.upper() for k in ["MG", "TABLET", "FTB", "KAPSUL", "FLAKON", "DOZ", "KREM"]):
                            break
                    except:
                        pass
                else:
                    continue
                break
            except Exception:
                pass
        time.sleep(2)

        # === 4. KONTROL MOTORU + RAPOR TABLOSU ===
        motor = ReceteKontrolMotoru(log_callback=lambda msg, tag="info": log(msg, tag))
        rapor_satirlari = []  # Excel rapor için

        sayac = 0
        onceki_ilaclar_str = None  # İlaç listesi değişimi ile tekrar tespiti
        tekrar_sayaci = 0

        while self.kontrol_aktif and sayac < 300:
            sayac += 1

            # Reçete no oku - koordinat kullanmadan, tüm 7 haneli alfanümerik text'lerden
            # İlk bulunan (genelde e-Reçete no veya takip no)
            recete_no = None
            try:
                for elem in self.medula.main_window.descendants(control_type="DataItem"):
                    try:
                        txt = elem.window_text()
                        if txt:
                            txt = txt.strip()
                            if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                                recete_no = txt
                                break
                    except:
                        pass
            except Exception:
                pass

            if not recete_no:
                # Sayfa henüz yüklenmemiş olabilir, biraz bekle
                time.sleep(3)
                try:
                    for elem in self.medula.main_window.descendants(control_type="DataItem"):
                        try:
                            txt = elem.window_text()
                            if txt:
                                txt = txt.strip()
                                if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                                    recete_no = txt
                                    break
                        except:
                            pass
                except Exception:
                    pass

            if not recete_no:
                log("Reçete no okunamadı - tarama tamamlandı", "info")
                break

            # Tekrar kontrolü - aynı ilaç listesi mi?
            if recete_no == onceki_ilaclar_str:
                tekrar_sayaci += 1
                if tekrar_sayaci >= 3:
                    log(f"Reçete değişmiyor ({recete_no}) - son sayfaya ulaşıldı", "info")
                    break
                # Tekrar dene
                for elem in self.medula.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "f:buttonSonraki":
                            elem.invoke()
                            break
                    except:
                        pass
                time.sleep(5)
                continue
            else:
                tekrar_sayaci = 0
                onceki_ilaclar_str = recete_no

            log(f"", "info")
            log(f"{'━' * 35}", "header")
            log(f"Reçete #{sayac}: {recete_no}", "header")

            # === 4a. REÇETE TÜRÜ KONTROL ===
            recete_turu = "Normal"
            for elem in self.medula.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    r = elem.rectangle()
                    if txt and r.top > 310 and r.top < 340:
                        txt = txt.strip()
                        if txt in ["Normal", "Kırmızı", "Yeşil", "Turuncu", "Mor"]:
                            recete_turu = txt
                            break
                except:
                    pass
            log(f"  Reçete türü: {recete_turu}", "info")

            # === 4b. RENKLİ REÇETE KONTROL ===
            renkli_durum = ""
            if recete_turu in ["Kırmızı", "Yeşil", "Mor"]:
                if not self.renkli_recete_listesi:
                    renkli_durum = "UYARI: Renkli reçete listesi yüklenmemiş!"
                    log(f"  ⚠ {renkli_durum}", "error")
                else:
                    # e-Reçete no ile ara
                    bulundu, kayit = self.renkli_recete_kontrol(recete_no)
                    if not bulundu:
                        # Medula'daki e-Reçete no'yu da dene
                        erecete_no = None
                        for elem in self.medula.main_window.descendants(control_type="DataItem"):
                            try:
                                txt = elem.window_text()
                                r = elem.rectangle()
                                if txt and r.top > 290 and r.top < 310 and r.left > 870:
                                    txt = txt.strip()
                                    if len(txt) >= 5 and txt.isalnum():
                                        erecete_no = txt
                                        break
                            except:
                                pass
                        if erecete_no:
                            bulundu, kayit = self.renkli_recete_kontrol(erecete_no)

                    if bulundu:
                        renkli_durum = "Renkli reçete sistemine işlenmiş ✓"
                        log(f"  ✓ {renkli_durum}", "success")
                    else:
                        renkli_durum = "SORUN: Renkli reçete sistemine İŞLENMEMİŞ!"
                        log(f"  ✗ {renkli_durum}", "error")

            # === 4c. İLAÇ SATIRLARINI OKU ===
            ilaclar = []
            items = []
            for elem in self.medula.main_window.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    r = elem.rectangle()
                    if txt and txt.strip() and r.top > 450 and r.top < 920:
                        items.append((txt.strip()[:100], r.top, r.left))
                except:
                    pass
            items.sort(key=lambda x: (x[1], x[2]))

            # İlaç adı anahtar kelimeleri (koordinat bağımsız algılama)
            ILAC_ANAHTAR = ["MG", "ML", "TABLET", "KAPSUL", "KAPSÜL", "TB", "FTB",
                            "DOZ", "INH", "GARGARA", "ŞURUP", "DAMLA", "AMPUL",
                            "FLAKON", "KREM", "JEL", "POMAD", "ENJEKT", "ŞASE",
                            "SURUP", "SPRAY", "FITIL", "SOLÜSYON", "SÜSPANSIYON",
                            "KALEM", "PATCH", "TOZU", "SACHET", "GRANÜL", "MERHEM",
                            "NEBUL", "EFF.", "ENTERIK", "FILM", "FORTE", "FORT"]
            ATLA = ["Maksimum", "Topl=", "KALEM", "Toplam Tutar", "Sayfaya",
                    "İncelemeye", "Botrastan", "Reçete Tutar", "YAZMIŞ",
                    "YAZMAMIŞ", "VERİLEMEZ", "KONTROL", "UZMAN",
                    "Uyumlu ICD", "Raporsuz", "Raporda DOZ", "Öncelik",
                    "Girilebilcek", "endikasyon",
                    "Günde", "Haftada", "Ayda", "Saatte", " x "]

            for txt, y, x in items:
                txt_upper = txt.upper()
                # İlaç adı: uzun text + ilaç formu anahtar kelimesi içerir
                if (len(txt) > 12 and any(k in txt_upper for k in ILAC_ANAHTAR)
                        and not txt.startswith("SGK") and not any(a in txt for a in ATLA)):
                    ilaclar.append({"ilac_adi": txt, "etkin_madde": "", "sgk_kodu": "", "rapor_kodu": "", "msj": ""})
                # Etkin madde: SGK ile başlar
                elif txt.startswith("SGK") and "-" in txt and ilaclar:
                    parts = txt.split("-", 1)
                    ilaclar[-1]["sgk_kodu"] = parts[0].strip()
                    ilaclar[-1]["etkin_madde"] = parts[1].strip() if len(parts) > 1 else ""
                # Rapor kodu: XX.XX formatı
                elif "." in txt and len(txt) <= 8 and txt[0].isdigit() and ilaclar:
                    # Tarih değil (dd/mm/yyyy)
                    if "/" not in txt:
                        ilaclar[-1]["rapor_kodu"] = txt
                # Mesaj: var/yok
                elif txt.lower() in ["var", "yok"] and ilaclar:
                    ilaclar[-1]["msj"] = txt.lower()

            if not ilaclar:
                log(f"  İlaç okunamadı, sonrakine geçiliyor", "warning")
                rapor_satirlari.append({
                    "recete_no": recete_no, "recete_turu": recete_turu,
                    "renkli_durum": renkli_durum, "ilac_adi": "-",
                    "etkin_madde": "-", "rapor_kodu": "-",
                    "sonuc": "Bakılamadı", "aciklama": "İlaç okunamadı"
                })
            else:
                log(f"  {len(ilaclar)} ilaç bulundu:", "info")

                # === 4d. HER İLAÇ İÇİN ALGORİTMİK KONTROL ===
                for ilac in ilaclar:
                    etkin = ilac.get("etkin_madde", "")
                    rapor_kodu = ilac.get("rapor_kodu", "")
                    msj = ilac.get("msj", "")

                    # DB'de kural var mı?
                    kural = None
                    if etkin:
                        kural = motor.kural_bul(etkin)
                        if not kural and ilac.get("sgk_kodu"):
                            kural = motor.kural_bul_sgk_kodu(ilac["sgk_kodu"])

                    # Yeni kural öğren
                    if not kural and etkin:
                        raporlu = 1 if rapor_kodu else 0
                        tip = "rapor_kontrolu" if raporlu else "raporsuz_verilebilir"
                        motor.yeni_kural_ekle(
                            etkin_madde=etkin,
                            sgk_kodu=ilac.get("sgk_kodu", ""),
                            rapor_kodu=rapor_kodu,
                            rapor_gerekli=raporlu,
                            kontrol_tipi=tip,
                            aciklama=f"Otomatik: {ilac['ilac_adi']}"
                        )
                        log(f"    [YENİ] {ilac['ilac_adi'][:40]} → {etkin}", "warning")

                    # Kontrol sonucu belirle
                    sonuc = "Uygun"
                    aciklama_str = ""

                    if kural:
                        if kural["rapor_gerekli"] and not rapor_kodu:
                            sonuc = "Uygun Değil"
                            aciklama_str = f"RAPOR GEREKLİ! SUT {kural.get('sut_maddesi', '?')}"
                            log(f"    [SORUN] {ilac['ilac_adi'][:35]} → {aciklama_str}", "error")
                        elif kural["rapor_gerekli"] and rapor_kodu:
                            sonuc = "Uygun"
                            aciklama_str = f"Raporlu ({rapor_kodu})"
                            log(f"    [  OK ] {ilac['ilac_adi'][:35]} → {aciklama_str}", "info")
                        else:
                            sonuc = "Uygun"
                            aciklama_str = "Raporsuz verilebilir"
                            log(f"    [  OK ] {ilac['ilac_adi'][:35]} → {aciklama_str}", "info")
                    elif etkin:
                        sonuc = "Şüpheli"
                        aciklama_str = "Yeni öğrenildi, SUT kontrolü yapılmadı"
                        log(f"    [  ?  ] {ilac['ilac_adi'][:35]} → {aciklama_str}", "warning")
                    else:
                        sonuc = "Bakılamadı"
                        aciklama_str = "Etkin madde okunamadı"
                        log(f"    [ --- ] {ilac['ilac_adi'][:35]} → {aciklama_str}", "warning")

                    if msj == "var":
                        aciklama_str += " | Mesaj VAR"

                    # === 4e. RAPOR TABLOSUNA YAZ ===
                    rapor_satirlari.append({
                        "recete_no": recete_no,
                        "recete_turu": recete_turu,
                        "renkli_durum": renkli_durum,
                        "ilac_adi": ilac["ilac_adi"][:50],
                        "etkin_madde": etkin,
                        "sgk_kodu": ilac.get("sgk_kodu", ""),
                        "rapor_kodu": rapor_kodu,
                        "msj": msj,
                        "sonuc": sonuc,
                        "aciklama": aciklama_str,
                    })

            # Durumu kaydet
            self.root.after(0, lambda r=recete_no, g=grup_kodu: self.grup_durumu_guncelle(g, r))

            # === 4f. SONRAKİ REÇETEYE GEÇ (invoke ile) ===
            sonraki_ok = False
            try:
                for elem in self.medula.main_window.descendants():
                    try:
                        if elem.element_info.automation_id == "f:buttonSonraki":
                            elem.invoke()
                            sonraki_ok = True
                            break
                    except:
                        pass
            except Exception:
                pass
            if not sonraki_ok:
                log("Sonraki butonu bulunamadı - tarama bitti", "info")
                break

            # Sayfa yüklenene kadar bekle (ilaç formu kelimesi görünene kadar)
            for bekle in range(12):
                time.sleep(1)
                try:
                    for elem in self.medula.main_window.descendants(control_type="DataItem"):
                        try:
                            txt = elem.window_text()
                            if txt and any(k in txt.upper() for k in ["MG", "TABLET", "FTB", "KAPSUL", "KREM"]):
                                break
                        except:
                            pass
                    else:
                        continue
                    break
                except Exception:
                    pass
            time.sleep(1)

        motor.kapat()

        # === 5. EXCEL RAPOR OLUŞTUR ===
        log(f"", "header")
        log(f"{'━' * 40}", "header")
        log(f"TARAMA TAMAMLANDI - {sayac} reçete kontrol edildi", "header")

        if rapor_satirlari:
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = f"{grup_adi} Kontrol"

                # Başlıklar
                basliklar = ["Reçete No", "Tür", "Renkli Reçete", "İlaç Adı",
                             "Etkin Madde", "SGK Kodu", "Rapor Kodu", "Msj",
                             "Sonuç", "Açıklama"]
                for col, b in enumerate(basliklar, 1):
                    c = ws.cell(row=1, column=col, value=b)
                    c.font = Font(bold=True, color="FFFFFF")
                    c.fill = PatternFill(start_color="1E3A5F", fill_type="solid")

                # Veriler
                renk_map = {
                    "Uygun": "C8E6C9",        # Yeşil
                    "Uygun Değil": "FFCDD2",   # Kırmızı
                    "Şüpheli": "FFF9C4",       # Sarı
                    "Bakılamadı": "E0E0E0",    # Gri
                }
                for row_idx, satir in enumerate(rapor_satirlari, 2):
                    ws.cell(row=row_idx, column=1, value=satir["recete_no"])
                    ws.cell(row=row_idx, column=2, value=satir["recete_turu"])
                    ws.cell(row=row_idx, column=3, value=satir["renkli_durum"])
                    ws.cell(row=row_idx, column=4, value=satir["ilac_adi"])
                    ws.cell(row=row_idx, column=5, value=satir["etkin_madde"])
                    ws.cell(row=row_idx, column=6, value=satir.get("sgk_kodu", ""))
                    ws.cell(row=row_idx, column=7, value=satir["rapor_kodu"])
                    ws.cell(row=row_idx, column=8, value=satir.get("msj", ""))
                    sonuc_cell = ws.cell(row=row_idx, column=9, value=satir["sonuc"])
                    ws.cell(row=row_idx, column=10, value=satir["aciklama"])
                    # Renklendirme
                    renk = renk_map.get(satir["sonuc"], "FFFFFF")
                    sonuc_cell.fill = PatternFill(start_color=renk, fill_type="solid")

                # Sütun genişlikleri
                for col_letter, width in [("A", 12), ("B", 8), ("C", 30), ("D", 45),
                                          ("E", 25), ("F", 12), ("G", 10), ("H", 5),
                                          ("I", 12), ("J", 45)]:
                    ws.column_dimensions[col_letter].width = width

                rapor_dosya = os.path.join(PROJE_DIZINI,
                    f"Kontrol_Raporu_{grup_kodu}_{secilen_donem.replace(' ', '_')}.xlsx")
                wb.save(rapor_dosya)
                log(f"Rapor kaydedildi: {rapor_dosya}", "success")

                # İstatistik
                uygun = sum(1 for s in rapor_satirlari if s["sonuc"] == "Uygun")
                sorunlu = sum(1 for s in rapor_satirlari if s["sonuc"] == "Uygun Değil")
                supheli = sum(1 for s in rapor_satirlari if s["sonuc"] == "Şüpheli")
                log(f"  Toplam ilaç: {len(rapor_satirlari)}", "info")
                log(f"  ✓ Uygun: {uygun}", "success")
                if sorunlu > 0:
                    log(f"  ✗ Sorunlu: {sorunlu}", "error")
                if supheli > 0:
                    log(f"  ? Şüpheli: {supheli}", "warning")
            except Exception as e:
                log(f"Rapor oluşturma hatası: {e}", "error")

        log(f"{'━' * 40}", "header")

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
