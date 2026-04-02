# -*- coding: utf-8 -*-
"""
Reçete Tarama Scripti - Subprocess olarak GUI'den çağrılır
Medula'daki reçeteleri tarar, ilaçları okur, SUT kurallarını kontrol eder.
Kullanım: python recete_tarama.py <grup> <donem_offset>
  grup: A, B, C, CK, GK
  donem_offset: 0=bu ay, 1=önceki ay, 2=iki ay önce...
"""

import sys
import time
import sqlite3
import pyautogui
from datetime import datetime
from pywinauto import Desktop

sys.stdout.reconfigure(encoding='utf-8')
pyautogui.FAILSAFE = False

DB_PATH = "kontrol_kurallari.db"
import os
LOG_DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tarama_log.txt")
_log_file = None

# ========== LOG ==========
def log(msg, level="info"):
    global _log_file
    zaman = datetime.now().strftime("%H:%M:%S")
    prefix = {"info": "[BİLGİ]", "ok": "[  OK  ]", "warn": "[UYARI]",
              "error": "[HATA!]", "header": "[=====]"}.get(level, "[?]")
    satir = f"{zaman} {prefix} {msg}"
    print(satir, flush=True)
    # Dosyaya da yaz
    try:
        if _log_file is None:
            _log_file = open(LOG_DOSYA, "w", encoding="utf-8")
        _log_file.write(satir + "\n")
        _log_file.flush()
    except:
        pass

# ========== MEDULA ==========
def medula_bul():
    desktop = Desktop(backend="uia")
    for w in desktop.windows():
        if "MEDULA" in w.window_text():
            return desktop.window(handle=w.handle)
    return None

def recete_no_oku(medula):
    """Açık reçetenin numarasını oku"""
    try:
        for elem in medula.descendants(control_type="DataItem"):
            try:
                txt = elem.window_text()
                if txt:
                    txt = txt.strip()
                    if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                        return txt
            except:
                pass
    except:
        pass
    return None

# ========== İLAÇ OKUMA ==========
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

def ilaclari_oku(medula):
    items = []
    try:
        for elem in medula.descendants(control_type="DataItem"):
            try:
                txt = elem.window_text()
                r = elem.rectangle()
                if txt and txt.strip() and r.top > 450 and r.top < 920:
                    items.append((txt.strip()[:100], r.top, r.left))
            except:
                pass
    except:
        pass
    items.sort(key=lambda x: (x[1], x[2]))

    ilaclar = []
    for txt, y, x in items:
        txt_upper = txt.upper()
        if (len(txt) > 12 and any(k in txt_upper for k in ILAC_ANAHTAR)
                and not txt.startswith("SGK") and not any(a in txt for a in ATLA)):
            ilaclar.append({"ilac_adi": txt, "etkin_madde": "", "sgk_kodu": "", "rapor_kodu": "", "msj": ""})
        elif txt.startswith("SGK") and "-" in txt and ilaclar:
            parts = txt.split("-", 1)
            ilaclar[-1]["sgk_kodu"] = parts[0].strip()
            ilaclar[-1]["etkin_madde"] = parts[1].strip() if len(parts) > 1 else ""
        elif "." in txt and "/" not in txt and len(txt) <= 8 and txt[0].isdigit() and ilaclar:
            ilaclar[-1]["rapor_kodu"] = txt
        elif txt.lower() in ["var", "yok"] and ilaclar:
            ilaclar[-1]["msj"] = txt.lower()
    return ilaclar

# ========== DB ==========
def db_kural_bul(cur, etkin_madde):
    if not etkin_madde:
        return None
    cur.execute("SELECT * FROM etkin_madde_kurallari WHERE etkin_madde = ? AND aktif = 1", (etkin_madde.upper(),))
    row = cur.fetchone()
    if row:
        return dict(row)
    cur.execute("SELECT * FROM etkin_madde_kurallari WHERE ? LIKE '%' || etkin_madde || '%' AND aktif = 1", (etkin_madde.upper(),))
    row = cur.fetchone()
    return dict(row) if row else None

def db_kaydet(cur, conn, etkin, sgk, rapor_kodu="", rapor_gerekli=0, tip="bilinmiyor", aciklama=""):
    try:
        cur.execute('''INSERT OR IGNORE INTO etkin_madde_kurallari
            (etkin_madde, sgk_kodu, sut_maddesi, rapor_kodu, rapor_gerekli, raporlu_maks_doz, kontrol_tipi, birlikte_yasaklar, aciklama, olusturma_tarihi, aktif)
            VALUES (?, ?, '', ?, ?, '', ?, '', ?, ?, 1)''',
            (etkin.upper(), sgk, rapor_kodu, rapor_gerekli, tip, aciklama, datetime.now().isoformat()))
        conn.commit()
        return True
    except:
        return False

def ilac_kontrol_et(cur, ilac):
    """Tek ilaç için SUT uygunluk kontrolü"""
    etkin = ilac.get("etkin_madde", "")
    rapor_kodu = ilac.get("rapor_kodu", "")
    msj = ilac.get("msj", "")
    ilac_adi = ilac.get("ilac_adi", "")

    kural = db_kural_bul(cur, etkin)
    if not kural:
        return "YENİ", "Veritabanında kural yok"

    sut = kural.get("sut_maddesi", "")
    sorunlar = []

    # 1. Rapor kontrolü
    if kural["rapor_gerekli"]:
        if not rapor_kodu:
            return "SORUN", f"RAPOR GEREKLİ ama yok! SUT {sut}"

    # 2. Rapor kodu uyumu - beklenen rapor kodu ile eşleşiyor mu?
    beklenen_rapor = kural.get("rapor_kodu", "")
    if rapor_kodu and beklenen_rapor and rapor_kodu != beklenen_rapor:
        # Bazı durumlarda farklı rapor kodları kabul edilebilir
        # Ama uyumsuzluk varsa uyar
        if rapor_kodu[:2] != beklenen_rapor[:2]:  # Tamamen farklı grup
            sorunlar.append(f"Rapor kodu uyumsuz: {rapor_kodu} (beklenen: {beklenen_rapor})")

    # 3. Mesaj kontrolü
    if msj == "var":
        sorunlar.append("Mesaj VAR - kontrol edilmeli")

    # Sonuç
    if sorunlar:
        detay = " | ".join(sorunlar)
        if any("RAPOR GEREKLİ" in s for s in sorunlar):
            return "SORUN", detay
        return "UYARI", f"Raporlu ({rapor_kodu}), SUT {sut} | {detay}"

    if kural["rapor_gerekli"]:
        return "OK", f"Raporlu ({rapor_kodu}), SUT {sut}"
    return "OK", f"Raporsuz verilebilir"

# ========== MEDULA NAVİGASYON ==========
def medula_navigasyon(medula, grup, donem_offset):
    """Reçete Listesi → Dönem → Fatura Türü → Sorgula → İlk reçeteye tıkla"""

    # 1. Reçete Listesi menüsü (invoke)
    log("Reçete Listesi sayfasına gidiliyor...", "info")
    for elem in medula.descendants():
        try:
            if elem.element_info.automation_id == "form1:menuHtmlCommandExButton31":
                elem.invoke()
                log("Reçete Listesi açıldı", "ok")
                break
        except:
            pass

    # Sayfa yüklenene kadar bekle
    for bekle in range(30):
        time.sleep(1)
        try:
            for elem in medula.descendants():
                try:
                    if elem.element_info.automation_id == "form1:buttonSonlandirilmamisReceteler":
                        log("Sayfa yüklendi", "ok")
                        break
                except:
                    pass
            else:
                continue
            break
        except:
            pass
    else:
        log("Sayfa yüklenemedi!", "error")
        return False

    # 2. Dönem seçimi (click_input + keyboard)
    if donem_offset > 0:
        log(f"Dönem seçiliyor (offset: {donem_offset})...", "info")
        for elem in medula.descendants():
            try:
                if elem.element_info.automation_id == "form1:menu2":
                    elem.click_input()
                    time.sleep(0.5)
                    for _ in range(donem_offset):
                        pyautogui.press("down")
                        time.sleep(0.15)
                    pyautogui.press("enter")
                    log("Dönem seçildi", "ok")
                    break
            except:
                pass
        time.sleep(1)

    # 3. Fatura Türü (click_input + 20 up + N down)
    grup_combo_index = {"A": 1, "B": 4, "C": 7, "CK": 10, "GK": 16}
    combo_idx = grup_combo_index.get(grup, 1)

    log(f"Fatura Türü: {grup} seçiliyor...", "info")
    for elem in medula.descendants():
        try:
            if elem.element_info.automation_id == "form1:menu1":
                elem.click_input()
                time.sleep(0.5)
                for _ in range(20):
                    pyautogui.press("up")
                    time.sleep(0.03)
                time.sleep(0.2)
                for _ in range(combo_idx):
                    pyautogui.press("down")
                    time.sleep(0.1)
                pyautogui.press("enter")
                log(f"Fatura Türü seçildi: {grup}", "ok")
                break
        except:
            pass
    time.sleep(1)

    # 4. Sorgula (invoke)
    log("Sorgula butonuna basılıyor...", "info")
    for elem in medula.descendants():
        try:
            if elem.element_info.automation_id == "form1:buttonSonlandirilmamisReceteler":
                elem.invoke()
                log("Sorgula tıklandı", "ok")
                break
        except:
            pass
    time.sleep(8)

    # 5. İlk reçeteye tıkla (click_input)
    for elem in medula.descendants(control_type="DataItem"):
        try:
            txt = elem.window_text()
            if txt:
                txt = txt.strip()
                if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                    elem.click_input()
                    log(f"İlk reçete: {txt}", "ok")
                    break
        except:
            pass
    else:
        log("Reçete bulunamadı!", "error")
        return False

    # İlaç tablosu yüklenene kadar bekle
    for bekle in range(15):
        time.sleep(1)
        try:
            for elem in medula.descendants(control_type="DataItem"):
                try:
                    txt = elem.window_text()
                    if txt and any(k in txt.upper() for k in ["MG", "TABLET", "FTB", "KAPSUL"]):
                        break
                except:
                    pass
            else:
                continue
            break
        except:
            pass
    time.sleep(2)
    return True

# ========== ANA TARAMA ==========
def tara(grup="A", donem_offset=0):
    log(f"{'='*50}", "header")
    log(f"REÇETE TARAMA - {grup} Grubu (offset: {donem_offset})", "header")
    log(f"{'='*50}", "header")

    medula = medula_bul()
    if not medula:
        log("MEDULA penceresi bulunamadı!", "error")
        return

    # Oturum kontrol
    oturum = False
    for elem in medula.descendants():
        try:
            if elem.element_info.automation_id == "form1:menuHtmlCommandExButton31":
                oturum = True
                break
        except:
            pass

    if not oturum:
        log("Oturum düşmüş, giriş butonu deneniyor...", "warn")
        for i in range(3):
            for elem in medula.descendants():
                try:
                    if elem.element_info.automation_id == "btnMedulayaGirisYap":
                        elem.click_input()
                        break
                except:
                    pass
            time.sleep(5)
            for elem in medula.descendants():
                try:
                    if elem.element_info.automation_id == "form1:menuHtmlCommandExButton31":
                        oturum = True
                        break
                except:
                    pass
            if oturum:
                break

        if not oturum:
            # Taskkill + restart
            log("Giriş butonu işe yaramadı, Medula yeniden başlatılıyor...", "warn")
            import subprocess as sp
            sp.run(["taskkill", "/F", "/IM", "BotanikMedula.exe"], capture_output=True, timeout=10)
            time.sleep(3)
            sp.Popen([r"C:\BotanikEczane\BotanikMedula.exe"])
            time.sleep(12)

            # Giriş penceresi
            desktop2 = Desktop(backend="uia")
            giris = None
            for w in desktop2.windows():
                t = w.window_text()
                if "BotanikEOS" in t and "(T)" in t and "EMRE" not in t:
                    giris = desktop2.window(handle=w.handle)
                    break
            if giris:
                giris.set_focus()
                time.sleep(0.5)
                for elem in giris.descendants():
                    try:
                        if elem.element_info.automation_id == "cmbKullanicilar":
                            elem.click_input()
                            time.sleep(0.5)
                            for item in elem.descendants(control_type="ListItem"):
                                if "botan" in item.window_text().lower():
                                    item.click_input()
                                    break
                            break
                    except:
                        pass
                time.sleep(0.3)
                for elem in giris.descendants():
                    try:
                        if elem.element_info.automation_id == "txtSifre":
                            elem.click_input()
                            time.sleep(0.2)
                            pyautogui.hotkey("ctrl", "a")
                            time.sleep(0.1)
                            elem.type_keys("152634", with_spaces=True)
                            break
                    except:
                        pass
                time.sleep(0.3)
                import win32gui
                for d in range(4):
                    for elem in giris.descendants():
                        try:
                            if elem.element_info.automation_id == "btnGirisYap":
                                elem.click_input()
                                break
                        except:
                            pass
                    time.sleep(3)
                    found = False
                    def chk(hwnd, _):
                        nonlocal found
                        if win32gui.IsWindowVisible(hwnd) and "MEDULA" in win32gui.GetWindowText(hwnd):
                            found = True
                    win32gui.EnumWindows(chk, None)
                    if found:
                        log("Medula yeniden açıldı!", "ok")
                        break

            # Yeni medula referansı al
            time.sleep(3)
            medula = medula_bul()
            if medula:
                for i in range(5):
                    for elem in medula.descendants():
                        try:
                            if elem.element_info.automation_id == "form1:menuHtmlCommandExButton31":
                                oturum = True
                                break
                        except:
                            pass
                    if oturum:
                        break
                    for elem in medula.descendants():
                        try:
                            if elem.element_info.automation_id == "btnMedulayaGirisYap":
                                elem.click_input()
                                break
                        except:
                            pass
                    time.sleep(4)

        if not oturum:
            log("Oturum başlatılamadı!", "error")
            return

    log("Medula bağlı ve oturum aktif", "ok")

    # Navigasyon
    if not medula_navigasyon(medula, grup, donem_offset):
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sayac = 0
    onceki_recete = None
    tekrar_sayaci = 0
    toplam_ilac = 0
    toplam_sorun = 0
    yeni_kural = 0

    while sayac < 300:
        sayac += 1

        recete_no = recete_no_oku(medula)

        # Tekrar kontrolü
        if recete_no == onceki_recete:
            tekrar_sayaci += 1
            if tekrar_sayaci >= 3:
                log(f"Reçete değişmiyor ({recete_no}) - tarama bitti", "info")
                break
            for elem in medula.descendants():
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
            onceki_recete = recete_no

        if not recete_no:
            time.sleep(3)
            recete_no = recete_no_oku(medula)
            if not recete_no:
                log("Reçete no okunamadı - tarama bitti", "info")
                break

        log(f"", "info")
        log(f"━━━ Reçete #{sayac}: {recete_no} ━━━", "header")

        ilaclar = ilaclari_oku(medula)

        if not ilaclar:
            log("İlaç okunamadı, sonrakine geçiliyor", "warn")
        else:
            log(f"  {len(ilaclar)} ilaç bulundu:", "info")
            for ilac in ilaclar:
                toplam_ilac += 1
                durum, aciklama = ilac_kontrol_et(cur, ilac)
                if durum == "YENİ" and ilac["etkin_madde"]:
                    raporlu = 1 if ilac["rapor_kodu"] else 0
                    tip = "rapor_kontrolu" if raporlu else "raporsuz_verilebilir"
                    if db_kaydet(cur, conn, ilac["etkin_madde"], ilac["sgk_kodu"],
                               ilac["rapor_kodu"], raporlu, tip, f"Otomatik: {ilac['ilac_adi']}"):
                        yeni_kural += 1
                    log(f"    [YENİ] {ilac['ilac_adi'][:40]} -> {ilac['etkin_madde']}", "warn")
                elif durum == "SORUN":
                    toplam_sorun += 1
                    log(f"    [SORUN] {ilac['ilac_adi'][:40]} -> {aciklama}", "error")
                elif durum == "UYARI":
                    log(f"    [UYARI] {ilac['ilac_adi'][:40]} -> {aciklama}", "warn")
                elif durum == "OK":
                    log(f"    [  OK ] {ilac['ilac_adi'][:40]} -> {aciklama}", "info")

        # Sonraki reçete (invoke)
        sonraki_ok = False
        try:
            for elem in medula.descendants():
                try:
                    if elem.element_info.automation_id == "f:buttonSonraki":
                        elem.invoke()
                        sonraki_ok = True
                        break
                except:
                    pass
        except:
            pass
        if not sonraki_ok:
            log("Sonraki butonu bulunamadı - tarama bitti", "info")
            break

        # Sayfa yüklenene kadar bekle
        for bekle in range(12):
            time.sleep(1)
            try:
                for elem in medula.descendants(control_type="DataItem"):
                    try:
                        txt = elem.window_text()
                        if txt and any(k in txt.upper() for k in ["MG", "TABLET", "FTB", "KAPSUL", "KREM"]):
                            break
                    except:
                        pass
                else:
                    continue
                break
            except:
                pass
        time.sleep(1)

    cur.execute("SELECT COUNT(*) FROM etkin_madde_kurallari")
    toplam_db = cur.fetchone()[0]
    conn.close()

    log(f"", "header")
    log(f"{'='*50}", "header")
    log(f"TARAMA TAMAMLANDI", "header")
    log(f"  Taranan reçete  : {sayac}", "info")
    log(f"  Toplam ilaç     : {toplam_ilac}", "info")
    log(f"  Sorunlu ilaç    : {toplam_sorun}", "error" if toplam_sorun > 0 else "info")
    log(f"  Yeni öğrenilen  : {yeni_kural}", "info")
    log(f"  DB toplam kural : {toplam_db}", "info")
    log(f"{'='*50}", "header")

    # Log dosyasını masaüstüne kopyala
    try:
        import shutil
        masaustu = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
        tarih = datetime.now().strftime("%Y%m%d_%H%M")
        hedef = os.path.join(masaustu, f"Tarama_Log_{grup}_{tarih}.txt")
        if os.path.exists(LOG_DOSYA):
            shutil.copy2(LOG_DOSYA, hedef)
            log(f"Log masaüstüne kaydedildi: {hedef}", "ok")
    except Exception as e:
        log(f"Log kopyalama hatası: {e}", "error")

if __name__ == "__main__":
    grup = sys.argv[1] if len(sys.argv) > 1 else "A"
    donem_offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    tara(grup=grup, donem_offset=donem_offset)
