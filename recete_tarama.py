# -*- coding: utf-8 -*-
"""
Reçete Tarama Scripti - Subprocess olarak GUI'den çağrılır
Medula'daki reçeteleri tarar, ilaçları okur, SUT kurallarını kontrol eder.
Kullanım: python recete_tarama.py <grup> <donem_offset>
  grup: A, B, C, CK, GK
  donem_offset: 0=bu ay, 1=önceki ay, 2=iki ay önce...

Durdurma: tarama_stop.flag dosyası oluşturulursa tarama durur.
"""

import sys
import os
import time
import json
import sqlite3
import pyautogui
from datetime import datetime
from pywinauto import Desktop

sys.stdout.reconfigure(encoding='utf-8')
pyautogui.FAILSAFE = False

PROJE_DIZINI = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJE_DIZINI, "kontrol_kurallari.db")
STOP_FILE = os.path.join(PROJE_DIZINI, "tarama_stop.flag")
GOTO_FILE = os.path.join(PROJE_DIZINI, "tarama_goto.flag")
AKTIVITE_FILE = os.path.join(PROJE_DIZINI, "medula_aktivite.tmp")
RENKLI_LISTE = os.path.join(PROJE_DIZINI, "renkli_recete_listesi.json")
LOG_DOSYA = os.path.join(PROJE_DIZINI, "tarama_log.txt")
_log_file = None


def aktivite_bildir():
    """Medula'ya her tıklamada/etkileşimde zaman damgası yaz.
    Keepalive bu dosyayı okuyarak son aktiviteyi takip eder."""
    try:
        with open(AKTIVITE_FILE, "w") as f:
            f.write(str(time.time()))
    except:
        pass


# ========== STOP KONTROL ==========
def durduruldu_mu():
    """Stop dosyası var mı kontrol et"""
    return os.path.exists(STOP_FILE)


def stop_temizle():
    """Eski stop ve goto dosyalarını sil"""
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
    except:
        pass
    try:
        if os.path.exists(GOTO_FILE):
            os.remove(GOTO_FILE)
    except:
        pass


def goto_recete_kontrol():
    """GUI'den geri dönme isteği var mı kontrol et.
    Returns: reçete no (str) veya None"""
    try:
        if os.path.exists(GOTO_FILE):
            with open(GOTO_FILE, "r") as f:
                recete_no = f.read().strip()
            os.remove(GOTO_FILE)
            return recete_no if recete_no else None
    except:
        pass
    return None


# ========== LOG ==========
def log(msg, level="info"):
    global _log_file
    zaman = datetime.now().strftime("%H:%M:%S")
    prefix = {"info": "[BİLGİ]", "ok": "[  OK  ]", "warn": "[UYARI]",
              "error": "[HATA!]", "header": "[=====]",
              "sorun": "[SORUN]", "yeni": "[YENİ]"}.get(level, "[?]")
    satir = f"{zaman} {prefix} {msg}"
    print(satir, flush=True)
    try:
        if _log_file is None:
            _log_file = open(LOG_DOSYA, "w", encoding="utf-8")
        _log_file.write(satir + "\n")
        _log_file.flush()
    except:
        pass


# ========== MEDULA ==========
def medula_bul():
    """BotanikEOS ana penceresini bul (Medula embedded browser burada).
    Title'da "MEDULA" olan veya kullanıcı adı içeren BotanikEOS penceresi aranır.
    Küçük şifre penceresi (kullanıcı adı yok) atlanır.
    """
    desktop = Desktop(backend="uia")
    for w in desktop.windows():
        try:
            title = w.window_text()
            if "MEDULA" in title:
                return desktop.window(handle=w.handle)
            if "BotanikEOS" in title and "(T)" in title:
                # Büyük ana pencere mi, küçük şifre penceresi mi?
                parcalar = title.replace("(T)", "").strip().split()
                if len(parcalar) >= 3:  # Kullanıcı adı var → ana pencere
                    return desktop.window(handle=w.handle)
        except:
            pass
    return None


def sistem_dusmus_mu(medula):
    """Medula 'Sistem hatası' sayfasında mı kontrol et.
    Kırmızı hata sayfası görünüyorsa True döner."""
    try:
        for d in medula.descendants():
            try:
                txt = d.window_text()
                if txt and "Sistem hatası" in txt:
                    return True
            except:
                pass
    except:
        pass
    return False


MEDULA_EXE = r"C:\BotanikEczane\BotanikMedula.exe"
MEDULA_KULLANICI = "16-botan"
MEDULA_SIFRE = "152634"


def medula_yeniden_baslat():
    """Medula sistem hatası sonrası hızlı kurtarma."""
    import subprocess

    medula = medula_bul()

    # 1. Giriş butonu dene (en hızlı - 3sn)
    if medula:
        log("Sistem hatası - Giriş butonu deneniyor...", "error")
        element_tikla(medula, "btnMedulayaGirisYap", "click")
        time.sleep(3)
        medula = medula_bul()
        if medula and not sistem_dusmus_mu(medula):
            if element_bul(medula, "form1:menuHtmlCommandExButton31") or element_bul(medula, "f:tbl1"):
                log("Giriş butonu ile düzeldi", "ok")
                return medula

    # 2. Taskkill + exe + giriş (10-15sn)
    log("Taskkill + yeniden başlat...", "error")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "BotanikMedula.exe"], capture_output=True, timeout=5)
    except:
        pass
    time.sleep(1)

    try:
        subprocess.Popen([MEDULA_EXE], cwd=os.path.dirname(MEDULA_EXE))
    except:
        log("BotanikMedula.exe başlatılamadı!", "error")
        return None

    # SifreSorForm bekle + hızlı giriş
    desktop = Desktop(backend="uia")
    for i in range(15):
        time.sleep(0.5)
        try:
            for w in desktop.windows():
                try:
                    if w.element_info.automation_id == "SifreSorForm":
                        w.set_focus()
                        time.sleep(0.2)
                        combo = w.child_window(auto_id="cmbKullanicilar")
                        combo.click_input()
                        time.sleep(0.2)
                        for item in combo.children():
                            try:
                                if "botan" in item.window_text().lower():
                                    item.click_input()
                                    break
                            except:
                                pass
                        time.sleep(0.2)
                        sifre = w.child_window(auto_id="txtSifre")
                        sifre.click_input()
                        time.sleep(0.1)
                        sifre.type_keys(MEDULA_SIFRE, with_spaces=True)
                        w.child_window(auto_id="btnGirisYap").click_input()
                        log("Giriş yapıldı", "info")
                        break
                except:
                    pass
            else:
                continue
            break
        except:
            pass

    # MEDULA penceresi bekle
    for i in range(15):
        time.sleep(1)
        medula = medula_bul()
        if medula and (element_bul(medula, "form1:menuHtmlCommandExButton31") or element_bul(medula, "f:tbl1")):
            log(f"Medula hazır ({i+1}s)", "ok")
            return medula

    log("Medula açılamadı!", "error")
    return None


def element_bul(medula, auto_id):
    """Tek bir elementi automation_id ile bul (child_window öncelikli - daha hızlı)"""
    try:
        cw = medula.child_window(auto_id=auto_id)
        if cw.exists(timeout=0.3):
            return cw.wrapper_object()
    except:
        pass
    # Fallback: descendants tarama (IE embedded browser elementleri child_window ile bulunamayabilir)
    try:
        for elem in medula.descendants():
            try:
                if elem.element_info.automation_id == auto_id:
                    return elem
            except:
                pass
    except:
        pass
    return None


def element_tikla(medula, auto_id, yontem="invoke"):
    """Element bul + tıkla + aktivite bildir. Tüm Medula etkileşimleri bu fonksiyonla yapılmalı."""
    elem = element_bul(medula, auto_id)
    if not elem:
        return False
    try:
        if yontem == "invoke":
            elem.invoke()
        else:
            elem.click_input()
        aktivite_bildir()
        return True
    except:
        return False


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


# ========== REÇETE TÜRÜ ==========
RECETE_TURLERI = {
    "1": "Normal", "2": "Kırmızı", "3": "Turuncu", "4": "Mor", "5": "Yeşil",
    "Normal": "Normal", "Kırmızı": "Kırmızı", "Turuncu": "Turuncu",
    "Mor": "Mor", "Yeşil": "Yeşil"
}

def recete_turu_oku(medula):
    """Reçete türünü oku - f:m4 SELECT combobox + DataItem fallback"""
    # Yöntem 1: f:m4 SELECT elementini oku
    try:
        elem = element_bul(medula, "f:m4")
        if elem:
            # selected_text() → "Normal", "Kırmızı", "Yeşil", "Mor", "Turuncu"
            try:
                selected = elem.selected_text()
                if selected and selected.strip() in RECETE_TURLERI:
                    return RECETE_TURLERI[selected.strip()]
            except:
                pass
            # Fallback: window_text
            val = elem.window_text().strip()
            if val in RECETE_TURLERI:
                return RECETE_TURLERI[val]
    except:
        pass

    # Yöntem 2: DataItem'lardan "Reçete Türü" yanındaki değeri oku
    try:
        for elem in medula.descendants(control_type="DataItem"):
            try:
                txt = elem.window_text().strip()
                r = elem.rectangle()
                # Reçete türü değeri genellikle y=362, x=865 civarında
                if txt in ["Normal", "Kırmızı", "Turuncu", "Mor", "Yeşil"]:
                    if r.top > 340 and r.top < 400:
                        return RECETE_TURLERI.get(txt, txt)
            except:
                pass
    except:
        pass

    # Yöntem 3: ComboBox'ların hepsini tara
    try:
        for elem in medula.descendants(control_type="ComboBox"):
            try:
                aid = elem.element_info.automation_id
                if aid == "f:m4":
                    # items() ile seçili değeri al
                    try:
                        for item in elem.children():
                            txt = item.window_text().strip()
                            if txt in RECETE_TURLERI:
                                return RECETE_TURLERI[txt]
                    except:
                        pass
            except:
                pass
    except:
        pass

    return "Normal"  # Varsayılan


# ========== RENKLİ REÇETE ==========
_renkli_liste_cache = None

def renkli_liste_yukle():
    """Renkli reçete listesini JSON'dan yükle (cache'le)"""
    global _renkli_liste_cache
    if _renkli_liste_cache is not None:
        return _renkli_liste_cache

    _renkli_liste_cache = set()
    try:
        if os.path.exists(RENKLI_LISTE):
            with open(RENKLI_LISTE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _renkli_liste_cache = set(data.get('receteler', []))
                log(f"Renkli reçete listesi yüklendi: {len(_renkli_liste_cache)} reçete", "info")
    except Exception as e:
        log(f"Renkli liste yüklenemedi: {e}", "warn")

    return _renkli_liste_cache


def renkli_recete_kontrol(recete_no, recete_turu):
    """Renkli reçete sisteme işlenmiş mi kontrol et.
    Returns: (sorun_var: bool, mesaj: str)
    """
    if recete_turu == "Normal":
        return False, "Beyaz reçete"

    # Renkli reçete - listede var mı?
    liste = renkli_liste_yukle()
    if not liste:
        return False, f"{recete_turu} reçete (liste yüklü değil, kontrol edilemedi)"

    if recete_no in liste:
        return False, f"{recete_turu} reçete - sisteme işlenmiş"
    else:
        return True, f"{recete_turu} reçete - SİSTEME İŞLENMEMİŞ!"


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
    """Reçete ilaç tablosundan ilaçları oku.
    Doz bilgisi de DataItem'lardan okunur ('1 Günde 4 x 2,00 - Adet' formatı).
    """
    # f:tbl1 pozisyonunu bul - ilaç tablosunun başlangıcı
    tbl_top = 0
    tbl_bottom = 9999
    try:
        tbl = element_bul(medula, "f:tbl1")
        if tbl:
            r = tbl.rectangle()
            tbl_top = r.top - 30  # biraz üstten başla
            tbl_bottom = r.bottom + 50
    except:
        pass

    items = []
    try:
        for elem in medula.descendants(control_type="DataItem"):
            try:
                txt = elem.window_text()
                r = elem.rectangle()
                if txt and txt.strip() and r.top >= tbl_top and r.top <= tbl_bottom:
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
            ilaclar.append({"ilac_adi": txt, "etkin_madde": "", "sgk_kodu": "",
                           "rapor_kodu": "", "msj": "",
                           "eos_rapor_doz_metin": ""})  # BotanikEOS yeşil şerit = RAPOR dozu
        elif txt.startswith("SGK") and "-" in txt and ilaclar:
            parts = txt.split("-", 1)
            ilaclar[-1]["sgk_kodu"] = parts[0].strip()
            ilaclar[-1]["etkin_madde"] = parts[1].strip() if len(parts) > 1 else ""
        elif "." in txt and "/" not in txt and len(txt) <= 8 and txt[0].isdigit() and ilaclar:
            ilaclar[-1]["rapor_kodu"] = txt
        elif txt.lower() in ["var", "yok"] and ilaclar:
            ilaclar[-1]["msj"] = txt.lower()
        elif _doz_satiri_mi(txt) and ilaclar and not ilaclar[-1]["eos_rapor_doz_metin"]:
            ilaclar[-1]["eos_rapor_doz_metin"] = txt  # Bu RAPOR dozu (BotanikEOS hesapladı)
    # === EK: Medula tablo ID'leri ile doğrulama/tamamlama ===
    # Rapor kodu ve mesaj bilgisini doğrudan element ID ile oku (DataItem sıralama hatasını önler)
    for i, ilac_item in enumerate(ilaclar):
        try:
            # Rapor kodu: f:tbl1:{i}:t9
            rk_elem = element_bul(medula, f"f:tbl1:{i}:t9")
            if rk_elem:
                rk_txt = (rk_elem.window_text() or "").strip()
                if rk_txt and rk_txt[0].isdigit():
                    ilac_item["rapor_kodu"] = rk_txt
            # Mesaj: f:tbl1:{i}:t11
            msj_elem = element_bul(medula, f"f:tbl1:{i}:t11")
            if msj_elem:
                msj_txt = (msj_elem.window_text() or "").strip().lower()
                if msj_txt in ["var", "yok"]:
                    ilac_item["msj"] = msj_txt
        except:
            pass

    return ilaclar


def _doz_satiri_mi(txt):
    """DataItem metninin doz satırı olup olmadığını kontrol et.
    Örnekler: '1 Günde 4 x 2,00 - Adet', '( Günde 2 x 1,000 Dozunda)'"""
    import re
    return bool(re.search(r'(G.nde|Haftada|Ayda|Y.lda|Saatte)\s+\d+\s*x\s*[\d,\.]+', txt))


# ========== DB ==========
def db_baglanti():
    """DB bağlantısı aç, tablolar yoksa oluştur"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Tablo yoksa oluştur
    cur.execute('''CREATE TABLE IF NOT EXISTS etkin_madde_kurallari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etkin_madde TEXT UNIQUE,
        sgk_kodu TEXT DEFAULT '',
        sut_maddesi TEXT DEFAULT '',
        rapor_kodu TEXT DEFAULT '',
        rapor_gerekli INTEGER DEFAULT 0,
        raporlu_maks_doz TEXT DEFAULT '',
        kontrol_tipi TEXT DEFAULT 'bilinmiyor',
        birlikte_yasaklar TEXT DEFAULT '',
        aciklama TEXT DEFAULT '',
        olusturma_tarihi TEXT,
        aktif INTEGER DEFAULT 1
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS ilac_mesaj_kurallari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etkin_madde TEXT DEFAULT '',
        ilac_adi_pattern TEXT DEFAULT '',
        mesaj_pattern TEXT DEFAULT '',
        sut_maddesi TEXT DEFAULT '',
        rapor_kodu TEXT DEFAULT '',
        aksiyon TEXT DEFAULT '',
        kosullar TEXT DEFAULT '',
        aciklama TEXT DEFAULT '',
        olusturma_tarihi TEXT,
        guncelleme_tarihi TEXT,
        aktif INTEGER DEFAULT 1
    )''')
    # Kontrol sonuçları tablosu (loglama)
    cur.execute('''CREATE TABLE IF NOT EXISTS kontrol_sonuclari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih TEXT,
        grup TEXT,
        recete_no TEXT,
        recete_turu TEXT,
        ilac_adi TEXT,
        etkin_madde TEXT,
        sgk_kodu TEXT,
        rapor_kodu TEXT,
        msj TEXT,
        kontrol_tipi TEXT,
        renkli_kontrol TEXT,
        uyari_kodu_kontrol TEXT,
        doz_kontrol TEXT,
        sut_kontrol TEXT,
        genel_sonuc TEXT,
        aciklama TEXT,
        recete_dozu TEXT,
        rapor_dozu TEXT,
        mesaj_metni TEXT
    )''')
    conn.commit()
    return conn, cur


def db_kural_bul(cur, etkin_madde):
    """Etkin maddeye göre kural bul"""
    if not etkin_madde:
        return None
    cur.execute("SELECT * FROM etkin_madde_kurallari WHERE etkin_madde = ? AND aktif = 1",
                (etkin_madde.upper(),))
    row = cur.fetchone()
    if row:
        return dict(row)
    cur.execute("SELECT * FROM etkin_madde_kurallari WHERE ? LIKE '%' || etkin_madde || '%' AND aktif = 1",
                (etkin_madde.upper(),))
    row = cur.fetchone()
    return dict(row) if row else None


def db_kaydet(cur, conn, etkin, sgk, rapor_kodu="", rapor_gerekli=0, tip="bilinmiyor", aciklama=""):
    """Yeni etkin madde kuralı kaydet"""
    try:
        cur.execute('''INSERT OR IGNORE INTO etkin_madde_kurallari
            (etkin_madde, sgk_kodu, sut_maddesi, rapor_kodu, rapor_gerekli,
             raporlu_maks_doz, kontrol_tipi, birlikte_yasaklar, aciklama, olusturma_tarihi, aktif)
            VALUES (?, ?, '', ?, ?, '', ?, '', ?, ?, 1)''',
            (etkin.upper(), sgk, rapor_kodu, rapor_gerekli, tip, aciklama,
             datetime.now().isoformat()))
        conn.commit()
        return True
    except:
        return False


# ========== İLAÇ KONTROL ==========
def ilac_kontrol_et(cur, ilac):
    """Tek ilaç için SUT uygunluk kontrolü
    Returns: (durum, aciklama)
      durum: OK, UYARI, SORUN, YENİ
    """
    etkin = ilac.get("etkin_madde", "")
    rapor_kodu = ilac.get("rapor_kodu", "")
    msj = ilac.get("msj", "")

    kural = db_kural_bul(cur, etkin)
    if not kural:
        return "YENİ", "Veritabanında kural yok"

    sut = kural.get("sut_maddesi", "")
    sorunlar = []

    # 1. Rapor kontrolü
    if kural["rapor_gerekli"]:
        if not rapor_kodu:
            return "SORUN", f"RAPOR GEREKLİ ama yok! SUT {sut}"

    # 2. Rapor kodu uyumu
    beklenen_rapor = kural.get("rapor_kodu", "")
    if rapor_kodu and beklenen_rapor and rapor_kodu != beklenen_rapor:
        if rapor_kodu[:2] != beklenen_rapor[:2]:
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


# ========== SONUÇ LOGLAMA (DB) ==========
def sonuc_logla(cur, conn, grup, recete_no, recete_turu, ilac, kontrol_tipi,
                renkli_k, uyari_k, doz_k, sut_k, genel, aciklama,
                recete_dozu="", rapor_dozu="", mesaj_metni=""):
    """Kontrol sonucunu veritabanına logla"""
    try:
        cur.execute('''INSERT INTO kontrol_sonuclari
            (tarih, grup, recete_no, recete_turu, ilac_adi, etkin_madde, sgk_kodu,
             rapor_kodu, msj, kontrol_tipi, renkli_kontrol, uyari_kodu_kontrol,
             doz_kontrol, sut_kontrol, genel_sonuc, aciklama, recete_dozu, rapor_dozu, mesaj_metni)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (datetime.now().isoformat(), grup, recete_no, recete_turu,
             ilac.get("ilac_adi", ""), ilac.get("etkin_madde", ""), ilac.get("sgk_kodu", ""),
             ilac.get("rapor_kodu", ""), ilac.get("msj", ""),
             kontrol_tipi, renkli_k, uyari_k, doz_k, sut_k, genel, aciklama,
             recete_dozu, rapor_dozu, mesaj_metni))
        conn.commit()
    except Exception as e:
        log(f"DB loglama hatası: {e}", "error")


# ========== CHECKBOX + İLAÇ BİLGİ PENCERESİ ==========
def checkbox_sec(medula, satir_idx):
    """İlaç satırının checkbox'ını seç (birden fazla yöntem dener)"""
    auto_id = f"f:tbl1:{satir_idx}:checkbox7"
    elem = element_bul(medula, auto_id)
    if not elem:
        return False
    # Yöntem 1: toggle
    try:
        elem.toggle()
        aktivite_bildir()
        time.sleep(0.3)
        return True
    except:
        pass
    # Yöntem 2: invoke
    try:
        elem.invoke()
        aktivite_bildir()
        time.sleep(0.3)
        return True
    except:
        pass
    # Yöntem 3: click_input
    try:
        elem.click_input()
        aktivite_bildir()
        time.sleep(0.3)
        return True
    except:
        pass
    return False


def ilac_bilgi_ac(medula):
    """İlaç Bilgi butonuna tıkla ve pencere açılana kadar bekle"""
    if not element_tikla(medula, "f:buttonIlacBilgiGorme"):
        log("    İlaç Bilgi butonu bulunamadı", "warn")
        return False

    # Pencere açılana kadar bekle (form1:textarea1 veya form1:buttonKapat)
    for _ in range(10):
        time.sleep(1)
        if element_bul(medula, "form1:buttonKapat"):
            time.sleep(0.5)
            return True
    log("    İlaç Bilgi penceresi açılmadı", "warn")
    # Kurtarma: Escape tuşu ile olası popup'ı kapat
    pyautogui.press("escape")
    time.sleep(1)
    return False


def ilac_bilgi_mesaj_oku(medula):
    """İlaç Bilgi penceresinden mesaj başlığı ve metin oku.
    Returns: (baslik_listesi, mesaj_metni)
    """
    basliklar = []
    mesaj_metni = ""

    # Mesaj başlıkları (birden fazla olabilir)
    for idx in range(10):
        auto_id = f"form1:tableExIlacMesajListesi:{idx}:text19"
        elem = element_bul(medula, auto_id)
        if not elem:
            break
        try:
            txt = elem.window_text()
            if txt and txt.strip():
                basliklar.append(txt.strip())
        except:
            pass

    # İlk başlığa tıkla (mesaj metnini yüklemek için)
    if basliklar:
        element_tikla(medula, "form1:tableExIlacMesajListesi:0:text19", "click")
        time.sleep(1)

    # Mesaj metni (textarea)
    elem = element_bul(medula, "form1:textarea1")
    if elem:
        try:
            mesaj_metni = elem.window_text() or ""
            mesaj_metni = mesaj_metni.strip()
        except:
            pass

    return basliklar, mesaj_metni


def ilac_bilgi_kapat(medula):
    """İlaç Bilgi penceresini kapat"""
    element_tikla(medula, "form1:buttonKapat")
    time.sleep(1)


def ilac_bilgi_ac_oku_kapat(medula, satir_idx):
    """Tam akış: checkbox seç → İlaç Bilgi aç → mesaj oku → kapat
    Returns: (basliklar, mesaj_metni) veya ([], "")
    """
    if not checkbox_sec(medula, satir_idx):
        log(f"    Checkbox seçilemedi (satır {satir_idx})", "warn")
        return [], ""

    if not ilac_bilgi_ac(medula):
        return [], ""

    basliklar, mesaj_metni = ilac_bilgi_mesaj_oku(medula)
    ilac_bilgi_kapat(medula)
    return basliklar, mesaj_metni


# ========== REÇETE DOZU OKUMA ==========
def medula_satir_idx_bul(medula, ilac_adi):
    """Medula tablo satır indeksini ilaç adıyla eşleştir.
    f:tbl1:0:t6, f:tbl1:1:t6... satırlarını tarar.
    Returns: int (satır indeksi) veya None
    """
    ilac_kisa = (ilac_adi or "").upper().split()[0] if ilac_adi else ""
    if not ilac_kisa:
        return None
    for row in range(20):
        elem = element_bul(medula, f"f:tbl1:{row}:t6")
        if not elem:
            break
        try:
            txt = (elem.window_text() or "").upper()
            if ilac_kisa in txt:
                return row
        except:
            pass
    return None


def recete_dozu_oku(medula, satir_idx, doz_metin=""):
    """Reçete ilaç satırından doz bilgilerini oku.
    Önce DataItem doz_metin'den parse eder (güvenilir).
    Fallback olarak Edit elementlerini dener.
    Returns: dict {adet, carpan, doz, periyot_sayi, periyot_birim, gunluk_doz} veya None
    """
    import re

    # Yöntem 1: DataItem doz metni parse et ("1 Günde 4 x 2,00 - Adet")
    if doz_metin:
        parsed = _doz_metin_parse(doz_metin)
        if parsed:
            return parsed

    # Yöntem 2: Edit elementlerinden oku (get_value - IE embedded input'ları)
    def oku_input(auto_id):
        elem = element_bul(medula, auto_id)
        if not elem:
            return 0.0
        val = ""
        # get_value() IE embedded input'lardan değer okur
        try:
            val = elem.get_value() or ""
        except:
            pass
        if not val:
            try:
                val = elem.iface_value.CurrentValue or ""
            except:
                pass
        if not val:
            try:
                lp = elem.legacy_properties()
                val = lp.get("Value", "") or ""
            except:
                pass
        if not val:
            val = elem.window_text() or ""
        val = val.strip().replace(",", ".")
        try:
            return float(val) if val else 0.0
        except:
            return 0.0

    adet = oku_input(f"f:tbl1:{satir_idx}:t2")
    carpan = oku_input(f"f:tbl1:{satir_idx}:t3")
    doz = oku_input(f"f:tbl1:{satir_idx}:t4")
    periyot_sayi = oku_input(f"f:tbl1:{satir_idx}:t5")

    periyot_birim = None  # None = okunamadı (varsayılan Günde yerine)
    elem = element_bul(medula, f"f:tbl1:{satir_idx}:m1")
    if elem:
        try:
            val = ""
            try:
                val = elem.get_value() or ""
            except:
                pass
            if not val:
                val = elem.window_text() or ""
            val = val.strip()
            birim_map = {"3": "Günde", "4": "Haftada", "5": "Ayda", "6": "Yılda",
                         "Günde": "Günde", "Haftada": "Haftada", "Ayda": "Ayda", "Yılda": "Yılda"}
            periyot_birim = birim_map.get(val)
        except:
            pass
    if not periyot_birim:
        periyot_birim = "Günde"  # Varsayılan (rapor dozu varsa karşılaştırmada düzeltilecek)

    if adet == 0 and doz == 0 and carpan == 0:
        return None

    carpan = carpan if carpan > 0 else 1.0
    doz = doz if doz > 0 else 1.0
    periyot_sayi = periyot_sayi if periyot_sayi > 0 else 1.0
    gunluk_doz = _gunluk_doz_hesapla(doz, carpan, periyot_sayi, periyot_birim)

    return {
        "adet": adet, "carpan": carpan, "doz": doz,
        "periyot_sayi": periyot_sayi, "periyot_birim": periyot_birim,
        "gunluk_doz": round(gunluk_doz, 2),
        "metin": f"{periyot_birim} {carpan} x {doz}"
    }


def _doz_metin_parse(doz_metin):
    """DataItem doz metnini parse et.
    Formatlar:
      '1 Günde 4 x 2,00 - Adet'
      '( Günde 2 x  1,000 Dozunda)'
    Returns: dict veya None
    """
    import re
    # Periyot birimi bul
    birim_match = re.search(r'(G\S*nde|Haftada|Ayda|Y\S*lda|Saatte)', doz_metin)
    if not birim_match:
        return None

    periyot_birim_raw = birim_match.group(1)
    # Normalize
    if "nde" in periyot_birim_raw.lower():
        periyot_birim = "Günde"
    elif "Hafta" in periyot_birim_raw:
        periyot_birim = "Haftada"
    elif "Ay" in periyot_birim_raw:
        periyot_birim = "Ayda"
    elif "lda" in periyot_birim_raw.lower():
        periyot_birim = "Yılda"
    else:
        periyot_birim = "Saatte"

    # Birimden önceki sayı (periyot sayısı) ve sonraki "çarpan x doz"
    before = doz_metin[:birim_match.start()]
    after = doz_metin[birim_match.end():]

    # Periyot sayısı (birimden önceki son sayı)
    periyot_match = re.search(r'(\d+)\s*$', before.strip())
    periyot_sayi = float(periyot_match.group(1)) if periyot_match else 1.0

    # Çarpan x Doz (birimden sonraki kısım)
    xdoz_match = re.search(r'(\d+)\s*x\s*([\d,\.]+)', after)
    if not xdoz_match:
        return None

    carpan = float(xdoz_match.group(1))
    doz = float(xdoz_match.group(2).replace(",", "."))

    gunluk_doz = _gunluk_doz_hesapla(doz, carpan, periyot_sayi, periyot_birim)

    return {
        "adet": 0, "carpan": carpan, "doz": doz,
        "periyot_sayi": periyot_sayi, "periyot_birim": periyot_birim,
        "gunluk_doz": round(gunluk_doz, 2),
        "metin": f"{periyot_birim} {periyot_sayi} x {doz}"
    }


def _gunluk_doz_hesapla(doz, carpan, periyot_sayi, periyot_birim):
    """Günlük doz hesapla"""
    carpan = carpan if carpan > 0 else 1.0
    periyot_sayi = periyot_sayi if periyot_sayi > 0 else 1.0
    gunluk = doz * carpan * periyot_sayi
    if "Hafta" in periyot_birim:
        gunluk /= 7.0
    elif "Ay" in periyot_birim:
        gunluk /= 30.0
    elif "Yıl" in periyot_birim or "Y\u0131l" in periyot_birim:
        gunluk /= 365.0
    return gunluk


# ========== RAPOR SAYFASI ==========
def rapor_ac(medula):
    """Rapor butonuna tıkla ve rapor sayfası açılana kadar bekle"""
    if not element_tikla(medula, "f:buttonRaporGoruntule"):
        log("    Rapor butonu bulunamadı", "warn")
        return False

    for _ in range(10):
        time.sleep(0.5)
        # Rapor sayfası yüklendiğinde Geri Dön butonu görünür
        if element_bul(medula, "form1:buttonGeriDon"):
            return True
        if element_bul(medula, "form1:tableEx1"):
            return True
    log("    Rapor sayfası açılmadı", "warn")
    return False


def rapor_tedavi_semasi_doz_oku(medula, etkin_madde_aranan):
    """Rapor tedavi şemasından eşleşen ilaç satırının dozunu oku.
    Returns: (doz_metni, gunluk_doz) veya (None, None)
    """
    etkin_upper = (etkin_madde_aranan or "").upper()

    for row in range(20):
        # Etkin madde
        auto_id = f"form1:tableEx1:{row}:text63"
        elem = element_bul(medula, auto_id)
        if not elem:
            break
        try:
            etkin = (elem.window_text() or "").strip().upper()
        except:
            continue

        # Eşleşme kontrolü (tam veya kısmi)
        if not etkin:
            continue
        if etkin_upper not in etkin and etkin not in etkin_upper:
            # Kısmi kelime eşleşmesi dene
            kelimeler = etkin_upper.split()
            if not any(k in etkin for k in kelimeler if len(k) > 3):
                continue

        # Tedavi şeması dozunu oku (text76: "Günde 1 x 1.0 Adet")
        doz_elem = element_bul(medula, f"form1:tableEx1:{row}:text76")
        if doz_elem:
            try:
                doz_metni = (doz_elem.window_text() or "").strip()
                if doz_metni:
                    # "Günde 1 x 1.0 Adet" formatını parse et
                    gunluk_doz = _rapor_doz_parse(doz_metni)
                    return doz_metni, gunluk_doz
            except:
                pass

    return None, None


def _rapor_doz_parse(doz_metni):
    """Rapor doz metnini parse et: 'Günde 1 x 1.0 Adet' → günlük doz float
    Format: {Periyot} {sayı} x {doz} {birim}
    """
    import re
    match = re.search(r'(\w+)\s+([\d,\.]+)\s*x\s*([\d,\.]+)', doz_metni)
    if not match:
        return None

    periyot = match.group(1)
    sayi = float(match.group(2).replace(",", "."))
    doz = float(match.group(3).replace(",", "."))

    gunluk = sayi * doz
    if "Hafta" in periyot:
        gunluk /= 7.0
    elif "Ay" in periyot:
        gunluk /= 30.0
    elif "Yıl" in periyot:
        gunluk /= 365.0

    return round(gunluk, 2)


def botanik_eos_doz_penceresi_oku():
    """BotanikEOS'un rapor sayfasına girildiğinde açtığı küçük doz penceresi.
    WinForms tablosu: grdUrunEtkin... - Etkin, Reçetedeki ilaç, Doz, Rapor Kodu sütunları.
    Returns: list of dict [{etkin, ilac, doz, rapor_kodu}, ...]
    """
    satirlar = []
    try:
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                # WinForms penceresi - küçük popup
                for child in w.descendants(control_type="Table"):
                    try:
                        aid = child.element_info.automation_id or ""
                        if "grdUrunEtkin" in aid:
                            # Satırları oku
                            for item in child.descendants(control_type="ListItem"):
                                try:
                                    satir_data = {}
                                    for cell in item.children():
                                        try:
                                            name = cell.window_text() or ""
                                            cell_name = cell.element_info.name or ""
                                            if "Etkin" in cell_name and "satır" in cell_name:
                                                satir_data["etkin"] = name
                                            elif "ilaç" in cell_name and "satır" in cell_name:
                                                satir_data["ilac"] = name
                                            elif "Doz" in cell_name and "satır" in cell_name:
                                                satir_data["doz"] = name
                                            elif "Rapor Kodu" in cell_name:
                                                satir_data["rapor_kodu"] = name
                                        except:
                                            pass
                                    if satir_data:
                                        satirlar.append(satir_data)
                                except:
                                    pass
                            return satirlar
                    except:
                        pass
            except:
                pass
    except:
        pass
    return satirlar


def erecete_aciklama_oku(medula):
    """E-Reçete Görüntüle sayfasını aç, açıklama ve tanı metinlerini oku, geri dön.
    Returns: dict {aciklamalar, tanilar, tum_metin} veya None
    """
    import pyautogui
    pyautogui.FAILSAFE = False

    btn = element_bul(medula, "f:buttonEreceteGoruntule")
    if not btn:
        return None

    btn.invoke()
    time.sleep(2)

    # Scroll ile tüm içeriği oku
    sonuc = {"aciklamalar": [], "tanilar": [], "tum_metin": ""}
    parcalar = []

    # 2 kere scroll yaparak tüm sayfayı oku
    for scroll_round in range(3):
        if scroll_round > 0:
            pyautogui.scroll(-5)
            time.sleep(0.5)

        for d in medula.descendants():
            try:
                txt = d.window_text() or ''
                ts = txt.strip()
                if len(ts) < 5:
                    continue
                r = d.rectangle()
                if r.top < 200:
                    continue

                parcalar.append(ts)

                tl = ts.lower()
                # Tanı metinleri
                if any(k in tl for k in ['diyabet', 'diabetes', 'mellitus', 'hipertansiyon',
                                          'astim', 'koah', 'kronik', 'insülin']):
                    if ts not in sonuc["tanilar"]:
                        sonuc["tanilar"].append(ts)

                # Açıklama metinleri (metformin, glisemik vb.)
                if any(k in tl for k in ['metformin', 'sülfonil', 'sulfonil', 'glisemik',
                                          'monoterapi', 'kontrol', 'tedavi edildi']):
                    if ts not in sonuc["aciklamalar"]:
                        sonuc["aciklamalar"].append(ts)
            except:
                pass

    sonuc["tum_metin"] = " ".join(set(parcalar))

    # Geri dön
    geri = element_bul(medula, "form1:buttonGeriDon")
    if geri:
        geri.invoke()
        time.sleep(1)

    return sonuc


def uyari_kodlari_oku(medula):
    """Reçete sayfasındaki uyarı kodlarını oku.
    Uyarı kodları reçete sayfasında ControlType.Text olarak görünüyor:
    '256 - Benign prostat hiperplazisi => XALFU XL 10 MG ...'
    Returns: list of dict [{kod, aciklama, ilac_adi}, ...]
    """
    import re
    kodlar = []
    bulunan = set()  # Tekrar engelleme
    try:
        # Uyarı kodu Text veya DataItem olabilir - ikisini de tara
        for d in medula.descendants():
            try:
                ctrl = d.element_info.control_type
                if ctrl not in ("ControlType.Text", "ControlType.DataItem", "ControlType.Custom"):
                    continue
                txt = d.window_text()
                if not txt or "=>" not in txt:
                    continue
                # Format: "256 - Açıklama => İLAÇ ADI"
                match = re.match(r'(\d+)\s*-\s*(.+?)\s*=>\s*(.+)', txt.strip())
                if match:
                    anahtar = f"{match.group(1)}_{match.group(3).strip()}"
                    if anahtar not in bulunan:
                        bulunan.add(anahtar)
                        kodlar.append({
                            "kod": match.group(1),
                            "aciklama": match.group(2).strip(),
                            "ilac_adi": match.group(3).strip(),
                        })
            except:
                pass
    except:
        pass
    if kodlar:
        log(f"  [OKU ] Uyarı kodları: {len(kodlar)} adet", "info")
        for uk in kodlar:
            log(f"    [OKU ] Uyarı {uk['kod']}: {uk['aciklama']} => {uk['ilac_adi']}", "info")
    return kodlar


def recete_teshisleri_oku(medula):
    """Reçete sayfasındaki teşhis satırlarını oku.
    f:tableEx1:{row}:text3 elementlerinden ICD tanı bilgileri.
    Returns: list of str
    """
    teshisler = []
    for row in range(20):
        auto_id = f"f:tableEx1:{row}:text3"
        elem = element_bul(medula, auto_id)
        if not elem:
            break
        try:
            txt = elem.window_text() or ""
            txt = txt.strip()
            if txt:
                teshisler.append(txt)
        except:
            pass
    return teshisler


def uyari_kodu_kontrol(uyari_kodlari, recete_teshisleri, rapor_aciklamalari, rapor_tanilari):
    """Uyarı kodlarının reçete/rapor teşhis ve açıklamalarıyla eşleşip eşleşmediğini kontrol et.
    Returns: list of dict [{kod, aciklama, ilac_adi, durum, eslesen_kaynak}, ...]
    """
    from recete_kontrol.sut_kontrolleri import _turkce_normalize

    # Tüm teşhis/tanı/açıklama metinlerini birleştir
    tum_metinler = []
    tum_metinler.extend(recete_teshisleri)
    tum_metinler.extend(rapor_aciklamalari)
    tum_metinler.extend(rapor_tanilari)
    birlesik = _turkce_normalize(" ".join(tum_metinler))

    sonuclar = []
    for uk in uyari_kodlari:
        aciklama_norm = _turkce_normalize(uk["aciklama"])
        # Açıklamadaki anahtar kelimeleri ara
        kelimeler = [k for k in aciklama_norm.split() if len(k) > 3]
        eslesme = 0
        for kelime in kelimeler:
            if kelime in birlesik:
                eslesme += 1

        if kelimeler:
            oran = eslesme / len(kelimeler)
        else:
            oran = 0

        if oran >= 0.5:  # Kelimelerin %50'si eşleşiyorsa uygun
            sonuclar.append({**uk, "durum": "UYGUN", "eslesen_oran": oran})
        else:
            sonuclar.append({**uk, "durum": "UYGUNSUZ", "eslesen_oran": oran})

    return sonuclar


def rapor_tum_metinleri_oku(medula):
    """Rapor sayfasındaki tüm açıklama, tanı, etkin madde, doz metinlerini topla.
    AutomationID yok - DataItem/Text/Custom elementlerinden pozisyon bazlı okur.
    Returns: dict {aciklamalar, tanilar, etkin_maddeler, dozlar, doktor_bransi, tum_metin}
    """
    sonuc = {
        "aciklamalar": [],
        "tanilar": [],
        "icd_kodlari": [],
        "etkin_maddeler": [],
        "dozlar": [],
        "doktor_bransi": "",
        "tum_metin": "",
    }

    tum_parcalar = []
    for d in medula.descendants():
        try:
            txt = d.window_text()
            if not txt or len(txt.strip()) < 3:
                continue
            r = d.rectangle()
            ctrl = d.element_info.control_type
            txt_s = txt.strip()

            # Sadece sayfa içeriği (y > 400, duyurular hariç)
            if r.top < 400:
                continue
            # Menü/duyuru filtreleme
            if txt_s.startswith("::") or txt_s.startswith("Tarih :") or "Konu :" in txt_s:
                continue

            tum_parcalar.append(txt_s)

            # Sınıflandır
            txt_upper = txt_s.upper()
            txt_lower = txt_s.lower()

            # Açıklama (uzun metin, SUT ibareleri)
            if len(txt_s) > 30 and any(k in txt_lower for k in
                    ["metformin", "sülfonil", "glisemik", "monoterapi", "kontrol",
                     "varfarin", "inr", "stent", "anjiografi", "ldl", "trigliserid",
                     "beta blok", "ejeksiyon", "dispne", "atak", "tedavi"]):
                sonuc["aciklamalar"].append(txt_s)

            # Tanı
            if "DİYABETES" in txt_upper or "DIABETES" in txt_upper or "MELLİTÜS" in txt_upper:
                sonuc["tanilar"].append(txt_s)
            if "HİPERTANSİYON" in txt_upper or "HYPERTENS" in txt_upper:
                sonuc["tanilar"].append(txt_s)
            if "ASTIM" in txt_upper or "KOAH" in txt_upper or "COPD" in txt_upper:
                sonuc["tanilar"].append(txt_s)

            # ICD kodu (E11.9, I10, J44 vb.)
            import re
            if re.match(r'^[A-Z]\d{2}(\.\d+)?$', txt_s):
                sonuc["icd_kodlari"].append(txt_s)

            # Rapor kodu + tanı satırı
            if re.match(r'^\d{2}\.\d{2}', txt_s):
                sonuc["tanilar"].append(txt_s)

            # Etkin madde (SGK kodu ile birlikte veya tek)
            if txt_s.startswith("SGK"):
                sonuc["etkin_maddeler"].append(txt_s)
            if "HCL" in txt_upper or "SODYUM" in txt_upper or "KALSIYUM" in txt_upper:
                if len(txt_s) < 60 and not any(c.isdigit() for c in txt_s[:3]):
                    sonuc["etkin_maddeler"].append(txt_s)

            # Rapor dozu
            if re.search(r'G.nde|Haftada|Ayda', txt_s) and 'x' in txt_s:
                sonuc["dozlar"].append(txt_s)

            # Doktor branşı
            if "Hastalıkları" in txt_s or "Kardiyoloji" in txt_s or "Nöroloji" in txt_s \
               or "Psikiyatri" in txt_s or "Göğüs" in txt_s or "Endokrin" in txt_s:
                sonuc["doktor_bransi"] = txt_s

        except:
            pass

    sonuc["tum_metin"] = " ".join(tum_parcalar)
    return sonuc


def rapor_ac_oku_geri_don(medula, satir_idx):
    """Tam akış: checkbox seç → rapor aç → tüm metinleri oku + BotanikEOS doz penceresi → geri dön.
    Returns: dict (rapor_tum_metinleri_oku sonucu + eos_dozlar) veya None
    """
    if not checkbox_sec(medula, satir_idx):
        log(f"    Checkbox seçilemedi (satır {satir_idx})", "warn")
        return None

    if not rapor_ac(medula):
        return None

    # 1. Medula rapor sayfasından metinleri oku
    sonuc = rapor_tum_metinleri_oku(medula)

    # 2. BotanikEOS'un açtığı küçük doz penceresinden oku
    time.sleep(1)  # Pencere açılması için kısa bekleme
    eos_dozlar = botanik_eos_doz_penceresi_oku()
    if eos_dozlar:
        sonuc["eos_dozlar"] = eos_dozlar
        for ed in eos_dozlar:
            log(f"    [OKU ] EOS Doz: {ed.get('etkin','?')[:20]} | Doz: {ed.get('doz','')} | R:{ed.get('rapor_kodu','')}", "info")

    if sonuc["aciklamalar"]:
        log(f"    Rapor açıklama: {sonuc['aciklamalar'][0]}", "info")
    if sonuc["tanilar"]:
        log(f"    [OKU ] Rapor tanı: {sonuc['tanilar'][0]}", "info")
    if sonuc["dozlar"]:
        log(f"    [OKU ] Rapor doz: {sonuc['dozlar'][0]}", "info")

    rapor_geri_don(medula)
    return sonuc


def rapor_geri_don(medula):
    """Rapor sayfasından reçete sayfasına geri dön"""
    if element_bul(medula, "form1:buttonGeriDon"):
        element_tikla(medula, "form1:buttonGeriDon")
    elif element_bul(medula, "f:buttonGeriDon"):
        return True
    time.sleep(1)
    for _ in range(8):
        if element_bul(medula, "f:tbl1") or element_bul(medula, "f:buttonSonraki"):
            return True
        time.sleep(0.5)
    # Son çare: f:buttonSonraki'yi ara (reçete sayfasında olduğumuzun kanıtı)
    if element_bul(medula, "f:tbl1"):
        return True
    return False


def rapor_ac_doz_oku_geri_don(medula, satir_idx, etkin_madde):
    """Tam akış: checkbox seç → rapor aç → doz oku → geri dön
    Returns: (rapor_doz_metni, rapor_gunluk_doz) veya (None, None)
    """
    if not checkbox_sec(medula, satir_idx):
        log(f"    Checkbox seçilemedi (satır {satir_idx})", "warn")
        return None, None

    if not rapor_ac(medula):
        return None, None

    doz_metni, gunluk_doz = rapor_tedavi_semasi_doz_oku(medula, etkin_madde)
    rapor_geri_don(medula)
    return doz_metni, gunluk_doz


# ========== DOZ KARŞILAŞTIRMA ==========
def doz_karsilastir(recete_gunluk, rapor_gunluk, recete_doz_dict=None, rapor_doz_dict=None):
    """Reçete dozu rapor dozunu geçiyor mu?
    recete_doz_dict/rapor_doz_dict: periyot_birim bilgisi için (opsiyonel)
    Returns: (uygun: bool, aciklama: str)
    """
    if recete_gunluk is None or rapor_gunluk is None:
        return True, "Doz bilgisi okunamadı, kontrol edilemedi"

    # Periyot birim uyumsuzluğu kontrolü:
    # Rapor "Ayda" reçete "Günde" ise büyük fark olur - muhtemelen SELECT okunamadı
    if recete_doz_dict and rapor_doz_dict:
        r_birim = recete_doz_dict.get("periyot_birim", "Günde")
        rp_birim = rapor_doz_dict.get("periyot_birim", "Günde")
        if r_birim == "Günde" and rp_birim in ("Ayda", "Haftada", "Yılda"):
            # Reçete birimi muhtemelen yanlış okundu (varsayılan Günde)
            # Rapor birimini kullanarak yeniden hesapla
            doz = recete_doz_dict.get("doz", 1.0)
            carpan = recete_doz_dict.get("carpan", 1.0)
            periyot_sayi = recete_doz_dict.get("periyot_sayi", 1.0)
            recete_gunluk = round(_gunluk_doz_hesapla(doz, carpan, periyot_sayi, rp_birim), 2)
            log(f"    [DOZ ] Periyot düzeltme: reçete 'Günde' → '{rp_birim}' (rapor referans)", "info")

    if recete_gunluk <= rapor_gunluk:
        return True, f"Doz uygun (reçete: {recete_gunluk} ≤ rapor: {rapor_gunluk})"
    else:
        return False, f"Doz aşımı! (reçete: {recete_gunluk} > rapor: {rapor_gunluk})"


# ========== SUT MESAJ KONTROL (sut_kontrolleri entegrasyonu) ==========
def sut_mesaj_kontrol(ilac, mesaj_basliklar, mesaj_metni):
    """Mesaj metni üzerinden SUT kontrolü yap.
    sut_kontrolleri modülünü kullanır.
    Returns: (sonuc: str, aciklama: str)  - "Uygun"/"UygunDegil"/"KontrolEdilemedi"
    """
    try:
        from recete_kontrol.sut_kontrolleri import sut_kontrol_yap

        ilac_sonuc = {
            "ilac_adi": ilac.get("ilac_adi", ""),
            "etkin_madde": ilac.get("etkin_madde", ""),
            "sgk_kodu": ilac.get("sgk_kodu", ""),
            "rapor_kodu": ilac.get("rapor_kodu", ""),
            "sut_maddesi": ilac.get("sut_maddesi", ""),
            "mesaj_metni": mesaj_metni,
            "mesaj_basliklar": mesaj_basliklar,
        }

        sonuc = sut_kontrol_yap(ilac_sonuc)
        if sonuc is None:
            return "KontrolEdilemedi", f"SUT kategorisi tespit edilemedi (mesaj: {mesaj_basliklar[:2]})"

        rapor = sonuc["kontrol_raporu"]
        kategori_adi = sonuc["kategori_adi"]

        if rapor.sonuc.value == "uygun":
            return "Uygun", f"SUT {kategori_adi}: {rapor.mesaj}"
        elif rapor.sonuc.value == "uygun_degil":
            return "UygunDegil", f"SUT {kategori_adi}: {rapor.mesaj}"
        else:
            return "KontrolEdilemedi", f"SUT {kategori_adi}: {rapor.mesaj}"

    except Exception as e:
        return "KontrolEdilemedi", f"SUT kontrol hatası: {e}"


# ========== İLAÇ KARAR AĞACI ==========
def ilac_detayli_kontrol(medula, cur, conn, grup, recete_no, recete_turu,
                          ilac, satir_idx, renkli_sonuc):
    """Tek ilaç için 4 durumlu karar ağacı (AA/BB/CC/DD).
    Returns: dict (rapor satırı)
    """
    rapor_var = bool(ilac.get("rapor_kodu", ""))
    msj_var = (ilac.get("msj", "") == "var")
    etkin = ilac.get("etkin_madde", "")
    ilac_adi = ilac.get("ilac_adi", "")[:45]

    # Medula tablo satır indeksini ilaç adıyla doğrula
    dogru_idx = medula_satir_idx_bul(medula, ilac.get("ilac_adi", ""))
    if dogru_idx is not None and dogru_idx != satir_idx:
        log(f"    [OKU ] Satır düzeltme: idx {satir_idx} → {dogru_idx} ({ilac_adi})", "info")
        satir_idx = dogru_idx

    # Mevcut DB kuralını da kontrol et
    kural = db_kural_bul(cur, etkin)

    # === BYPASS KONTROLÜ: İlaç kontrol ayarlarını sorgula ===
    try:
        from kontrol_kurallari import get_kontrol_ayarlari, get_ogrenilen_ilaclar
        ayarlar = get_kontrol_ayarlari()
        ogrenilen = get_ogrenilen_ilaclar()

        # İlacı öğrenilen veritabanına kaydet
        ogrenilen.ilac_kaydet(
            ilac.get("ilac_adi", ""), etkin_madde=etkin,
            sgk_kodu=ilac.get("sgk_kodu"), rapor_kodu=ilac.get("rapor_kodu")
        )

        # Öğrenilen ilaçtan ATC/farmakolojik grup bilgisi al
        ilac_kayit = ogrenilen.ilac_bul(ilac.get("ilac_adi", ""))
        atc_grup = ilac_kayit.get("atc_grup") if ilac_kayit else None
        farm_grup = ilac_kayit.get("farmakolojik_grup") if ilac_kayit else None

        bypass_sut = not ayarlar.kontrol_aktif_mi(
            "sut", ilac_adi=ilac.get("ilac_adi", ""), etkin_madde=etkin,
            atc_grup=atc_grup, farmakolojik_grup=farm_grup)
        bypass_doz = not ayarlar.kontrol_aktif_mi(
            "doz", ilac_adi=ilac.get("ilac_adi", ""), etkin_madde=etkin,
            atc_grup=atc_grup, farmakolojik_grup=farm_grup)
        bypass_mesaj = not ayarlar.kontrol_aktif_mi(
            "ilac_mesaji", ilac_adi=ilac.get("ilac_adi", ""), etkin_madde=etkin,
            atc_grup=atc_grup, farmakolojik_grup=farm_grup)

        # İlaç mesajı bypass ise msj_var'ı False yap (mesaj yokmuş gibi davran)
        if bypass_mesaj and msj_var:
            msj_var = False
            log(f"    [BYPASS] {ilac_adi} → İlaç mesajı kontrolü pasif (ayar)", "info")
    except Exception as e:
        bypass_sut = False
        bypass_doz = False
        bypass_mesaj = False
        atc_grup = None
        farm_grup = None
        logger.debug(f"Kontrol ayarları yüklenemedi: {e}")

    # Varsayılan sonuçlar
    kontrol_tipi = ""
    doz_k = "-"
    sut_k = "-"
    genel = ""
    aciklama = ""
    recete_dozu_str = ""
    rapor_dozu_str = ""
    mesaj_metni = ""
    aciklama_parcalari = []
    rapor_verisi = None
    erecete = None

    # ═══ DURUM AA: Raporsuz + Mesajsız → GEÇ ═══
    if not rapor_var and not msj_var:
        kontrol_tipi = "AA"
        genel = "GECİLDİ"
        aciklama = "Raporsuz, mesajsız - kontrol gerekmez"
        log(f"    [GEÇ ] {ilac_adi} → Raporsuz, mesajsız", "info")

    # ═══ DURUM BB: Raporsuz + Mesaj VAR → Reçete/E-Reçete açıklamaları oku + SUT kontrol ═══
    elif not rapor_var and msj_var:
        kontrol_tipi = "BB"
        log(f"    [OKU ] {ilac_adi} → Raporsuz ama mesaj VAR", "warn")

        # SUT bypass kontrolü
        if bypass_sut:
            sut_k = "Bypass"
            aciklama_parcalari.append("SUT kontrolü pasif (ayar)")
            genel = "GECİLDİ"
            log(f"    [BYPASS] {ilac_adi} → SUT kontrolü pasif (ayar)", "info")
        else:
            # Reçete teşhisleri oku
            recete_teshisleri = recete_teshisleri_oku(medula)
            recete_metin = " ".join(recete_teshisleri)
            if recete_teshisleri:
                log(f"    [OKU ] Reçete teşhis: {recete_teshisleri[0]}", "info")

            # E-Reçete açıklamalarını da oku
            erecete = erecete_aciklama_oku(medula)
            if erecete:
                if erecete["aciklamalar"]:
                    log(f"    [OKU ] E-Reçete açıklama: {erecete['aciklamalar'][0]}", "info")
                    recete_metin += " " + erecete["tum_metin"]
                if erecete["tanilar"]:
                    log(f"    [OKU ] E-Reçete tanı: {erecete['tanilar'][0]}", "info")
                    recete_metin += " " + " ".join(erecete["tanilar"])

            sut_sonuc, sut_aciklama = sut_mesaj_kontrol(ilac, [], recete_metin)
            sut_k = sut_sonuc
            aciklama_parcalari.append(sut_aciklama)

            if sut_sonuc == "Uygun":
                genel = "UYGUN"
                log(f"    [SUT ] {sut_aciklama}", "info")
                log(f"    [  OK ] SUT uygun", "ok")
            elif sut_sonuc == "UygunDegil":
                genel = "UYGUNSUZ"
                log(f"    [SUT ] {sut_aciklama}", "info")
                log(f"    [SORUN] SUT uygunsuz", "sorun")
            else:
                genel = "KONTROLEDİLEMEDİ"
                log(f"    [SUT ] {sut_aciklama}", "warn")
                if "kategorisi tespit edilemedi" in sut_aciklama:
                    _ai_sut_implementasyon_iste(ilac_adi, ilac.get("etkin_madde", ""),
                                                rapor_kodu=ilac.get("rapor_kodu", ""))

    # ═══ DURUM CC: Raporlu + Mesajsız → Doz karşılaştır (yeşil şerit = rapor dozu) ═══
    elif rapor_var and not msj_var:
        kontrol_tipi = "CC"

        if bypass_doz:
            doz_k = "Bypass"
            aciklama_parcalari.append("Doz kontrolü pasif (ayar)")
            genel = "GECİLDİ"
            log(f"    [BYPASS] {ilac_adi} → Doz kontrolü pasif (ayar)", "info")
        else:
            eos_rapor_doz = ilac.get("eos_rapor_doz_metin", "")
            rapor_doz_parsed = _doz_metin_parse(eos_rapor_doz) if eos_rapor_doz else None
            recete_doz = recete_dozu_oku(medula, satir_idx, "")

            if rapor_doz_parsed:
                rapor_dozu_str = eos_rapor_doz
                rapor_gunluk = rapor_doz_parsed["gunluk_doz"]

                if recete_doz:
                    recete_dozu_str = recete_doz["metin"]
                    recete_gunluk = recete_doz["gunluk_doz"]
                    log(f"    [OKU ] Rapor doz: {eos_rapor_doz} | Reçete doz: {recete_dozu_str}", "info")
                    uygun, doz_aciklama = doz_karsilastir(recete_gunluk, rapor_gunluk, recete_doz, rapor_doz_parsed)
                    doz_k = "Uygun" if uygun else "UygunDegil"
                    aciklama_parcalari.append(doz_aciklama)
                    if uygun:
                        genel = "UYGUN"
                        log(f"    [  OK ] {doz_aciklama}", "ok")
                    else:
                        genel = "UYGUNSUZ"
                        log(f"    [SORUN] {doz_aciklama}", "sorun")
                else:
                    doz_k = "Uygun"
                    aciklama_parcalari.append(f"Rapor doz: {eos_rapor_doz}, reçete doz okunamadı")
                    genel = "UYGUN"
                    log(f"    [OKU ] Rapor doz: {eos_rapor_doz} | Reçete doz: okunamadı", "info")
            else:
                doz_k = "Uygun"
                aciklama_parcalari.append(f"Raporlu ({ilac['rapor_kodu']}), doz şeridi okunamadı")
                genel = "UYGUN"
                log(f"    [OKU ] Raporlu ({ilac['rapor_kodu']}), doz şeridi okunamadı", "info")

    # ═══ DURUM DD: Raporlu + Mesaj VAR → Doz karşılaştır + SUT kontrol ═══
    elif rapor_var and msj_var:
        kontrol_tipi = "DD"
        log(f"    [OKU ] {ilac_adi} → Raporlu ({ilac['rapor_kodu']}) + Mesaj VAR", "warn")

        # 1. Doz karşılaştırma
        uygun_doz = True
        if bypass_doz:
            doz_k = "Bypass"
            aciklama_parcalari.append("Doz kontrolü pasif (ayar)")
            log(f"    [BYPASS] {ilac_adi} → Doz kontrolü pasif (ayar)", "info")
        else:
            eos_rapor_doz = ilac.get("eos_rapor_doz_metin", "")
            rapor_doz_parsed = _doz_metin_parse(eos_rapor_doz) if eos_rapor_doz else None
            recete_doz = recete_dozu_oku(medula, satir_idx, "")

            if rapor_doz_parsed and recete_doz:
                recete_dozu_str = recete_doz["metin"]
                rapor_gunluk = rapor_doz_parsed["gunluk_doz"]
                log(f"    [OKU ] Rapor doz: {eos_rapor_doz} | Reçete doz: {recete_dozu_str}", "info")
                uygun_doz, doz_aciklama_detay = doz_karsilastir(recete_doz["gunluk_doz"], rapor_gunluk, recete_doz, rapor_doz_parsed)
                doz_k = "Uygun" if uygun_doz else "UygunDegil"
                aciklama_parcalari.append(doz_aciklama_detay)
                if uygun_doz:
                    log(f"    [  OK ] Doz: {doz_aciklama_detay}", "ok")
                else:
                    log(f"    [SORUN] Doz: {doz_aciklama_detay}", "sorun")
            elif eos_rapor_doz:
                log(f"    [OKU ] Rapor doz: {eos_rapor_doz} | Reçete doz: okunamadı", "info")

        # 2. SUT kontrol
        if bypass_sut:
            sut_k = "Bypass"
            aciklama_parcalari.append("SUT kontrolü pasif (ayar)")
            log(f"    [BYPASS] {ilac_adi} → SUT kontrolü pasif (ayar)", "info")
        else:
            rapor_verisi = rapor_ac_oku_geri_don(medula, satir_idx)
            rapor_metin = rapor_verisi["tum_metin"] if rapor_verisi else ""
            if rapor_verisi:
                log(f"    [OKU ] Rapor açıklama okundu ({len(rapor_metin)} kr)", "info")

            sut_sonuc, sut_aciklama = sut_mesaj_kontrol(ilac, [], rapor_metin)
            sut_k = sut_sonuc
            aciklama_parcalari.append(sut_aciklama)

            if sut_sonuc == "Uygun":
                log(f"    [SUT ] {sut_aciklama}", "info")
                log(f"    [  OK ] SUT uygun", "ok")
            elif sut_sonuc == "UygunDegil":
                log(f"    [SUT ] {sut_aciklama}", "info")
                log(f"    [SORUN] SUT uygunsuz", "sorun")
            else:
                log(f"    [SUT ] {sut_aciklama}", "warn")
                if "kategorisi tespit edilemedi" in sut_aciklama or "Rapor/mesaj metni yok" in sut_aciklama:
                    _ai_sut_implementasyon_iste(ilac_adi, etkin, rapor_kodu=ilac.get("rapor_kodu", ""),
                                                mesaj_metni=rapor_metin[:300] if rapor_metin else "")

        # Genel sonuç
        if not uygun_doz or sut_k == "UygunDegil":
            genel = "UYGUNSUZ"
        elif (sut_k in ("Uygun", "Bypass")) and uygun_doz:
            genel = "UYGUN" if sut_k == "Uygun" else "GECİLDİ"
        else:
            genel = "KONTROLEDİLEMEDİ"

    aciklama = " | ".join(aciklama_parcalari) if aciklama_parcalari else aciklama

    # DB'ye logla
    sonuc_logla(cur, conn, grup, recete_no, recete_turu, ilac, kontrol_tipi,
                renkli_sonuc, "-", doz_k, sut_k, genel, aciklama,
                recete_dozu_str, rapor_dozu_str, mesaj_metni)

    # Rapor/teşhis verisi (uyarı kodu kontrolünde kullanılacak)
    rapor_bilgi = {}
    if kontrol_tipi == "DD" and rapor_verisi:
        rapor_bilgi = rapor_verisi
    elif kontrol_tipi == "BB" and erecete:
        rapor_bilgi = erecete

    # Rapor satırı (JSON/Excel için)
    return {
        "recete_no": recete_no, "recete_turu": recete_turu,
        "ilac_adi": ilac["ilac_adi"], "etkin_madde": ilac.get("etkin_madde", ""),
        "rapor_kodu": ilac.get("rapor_kodu", ""), "msj": ilac.get("msj", ""),
        "renkli_kontrol": "-",
        "rapor_kontrol": doz_k if doz_k != "-" else "-",
        "sut_kontrol": sut_k if sut_k != "-" else "-",
        "sonuc": genel, "aciklama": aciklama,
        "_rapor_verisi": rapor_bilgi,  # iç kullanım: uyarı kodu kontrolü için
    }


# ========== MEDULA NAVİGASYON ==========
def medula_navigasyon(medula, grup, donem_offset):
    """Reçete Listesi → Dönem → Fatura Türü → Sorgula → İlk reçeteye tıkla"""

    # 0. webBrowser1'e focus ver (IE embedded browser)
    try:
        for c in medula.children():
            try:
                if c.element_info.automation_id == "webBrowser1":
                    c.set_focus()
                    time.sleep(0.3)
                    break
            except:
                pass
    except:
        pass

    # 1. Reçete Listesi menüsü (invoke)
    log("Reçete Listesi sayfasına gidiliyor...", "info")
    for deneme in range(3):
        if element_tikla(medula, "form1:menuHtmlCommandExButton31"):
            log("Reçete Listesi açıldı", "ok")
        else:
            # Menü görünmüyor — reçete sayfasında olabiliriz
            # BotanikEOS Giriş butonu ile ana sayfaya dön
            log("Menü görünmüyor, ana sayfaya dönülüyor...", "warn")
            element_tikla(medula, "btnMedulayaGirisYap", "click")
            time.sleep(5)
            # Tekrar dene
            if element_tikla(medula, "form1:menuHtmlCommandExButton31"):
                log("Reçete Listesi açıldı (giriş butonu sonrası)", "ok")
            else:
                log("Reçete Listesi menüsü bulunamadı!", "error")
                return False

        # Sayfa yüklenene kadar bekle
        for bekle in range(15):
            time.sleep(1)
            if durduruldu_mu():
                log("DURDURULDU", "warn")
                return False
            if element_bul(medula, "form1:buttonSonlandirilmamisReceteler"):
                log("Sayfa yüklendi", "ok")
                break
        else:
            if deneme < 2:
                log(f"Sayfa yüklenemedi, tekrar deneniyor ({deneme+2}/3)...", "warn")
                time.sleep(2)
                continue
            log("Sayfa yüklenemedi!", "error")
            return False
        break  # Başarılı

    # 2. Dönem seçimi
    if donem_offset > 0:
        log(f"Dönem seçiliyor (offset: {donem_offset})...", "info")
        if element_tikla(medula, "form1:menu2", "click"):
            time.sleep(0.5)
            for _ in range(donem_offset):
                pyautogui.press("down")
                time.sleep(0.15)
            pyautogui.press("enter")
            log("Dönem seçildi", "ok")
        time.sleep(1)

    # 3. Fatura Türü
    grup_combo_index = {"A": 1, "B": 4, "C": 7, "CK": 10, "GK": 16}
    combo_idx = grup_combo_index.get(grup, 1)

    log(f"Fatura Türü: {grup} seçiliyor...", "info")
    if element_tikla(medula, "form1:menu1", "click"):
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
    time.sleep(1)

    # 4. Sorgula
    log("Sorgula butonuna basılıyor...", "info")
    if element_tikla(medula, "form1:buttonSonlandirilmamisReceteler"):
        log("Sorgula tıklandı", "ok")

    # Reçete listesi yüklenene kadar bekle (max 8 sn)
    for _ in range(16):
        time.sleep(0.5)
        try:
            for elem in medula.descendants(control_type="DataItem"):
                txt = (elem.window_text() or "").strip()
                if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                    break
            else:
                continue
            break
        except:
            pass

    # 5. İlk reçeteye tıkla
    ilk_recete_bulundu = False
    try:
        for elem in medula.descendants(control_type="DataItem"):
            try:
                txt = elem.window_text()
                if txt:
                    txt = txt.strip()
                    if len(txt) == 7 and txt[0].isdigit() and txt.isalnum():
                        elem.click_input()
                        aktivite_bildir()
                        log(f"İlk reçete: {txt}", "ok")
                        ilk_recete_bulundu = True
                        break
            except:
                pass
    except:
        pass
    if not ilk_recete_bulundu:
        log("Reçete bulunamadı!", "error")
        return False

    # İlaç tablosu yüklenene kadar bekle
    for bekle in range(6):
        time.sleep(0.5)
        if element_bul(medula, "f:tbl1:0:t6"):  # İlk ilaç adı hücresi
            break
    time.sleep(0.5)
    return True


# ========== MEDULA OTURUM ==========
def oturum_kontrol_ve_baglan(medula):
    """Oturum aktif mi kontrol et. Sistem hatası varsa yeniden başlat."""
    # Sistem hatası kontrolü
    if sistem_dusmus_mu(medula):
        log("Sistem hatası tespit edildi - yeniden başlatılıyor...", "error")
        return medula_yeniden_baslat()

    # Reçete sayfası elementleri varsa oturum aktiftir (en hızlı kontrol)
    if element_bul(medula, "f:tbl1") or element_bul(medula, "f:buttonSonraki"):
        return medula

    # Menü görünüyor mu?
    if element_bul(medula, "form1:menuHtmlCommandExButton31"):
        return medula  # Oturum aktif

    # BotanikEOS toolbar butonları görünüyorsa pencere açık, oturum düşmüş olabilir
    # Giriş butonuna basarak yenilemeyi dene
    log("Oturum düşmüş, giriş butonu deneniyor...", "warn")
    element_tikla(medula, "btnMedulayaGirisYap", "click")
    time.sleep(5)
    if element_bul(medula, "form1:menuHtmlCommandExButton31"):
        log("Oturum yenilendi", "ok")
        return medula
    if element_bul(medula, "f:tbl1"):
        return medula

    log("Oturum düşmüş - yeniden başlatılıyor...", "error")
    return medula_yeniden_baslat()


# ========== RAPOR ==========
DURUM_DOSYASI = os.path.join(PROJE_DIZINI, "recete_kontrol_durumlari.json")
AI_IMPL_DOSYA = os.path.join(PROJE_DIZINI, "ai_impl_kuyruk.json")  # AI implementasyon kuyruğu


_ai_istenen_ilaclar = set()  # Aynı ilaç için tekrar AI açma

def _ai_claude_calistir(prompt, timeout=180, dosya_yazabilir=False):
    """Claude CLI çalıştır ve sonucu döndür. Bloklar."""
    import subprocess as sp
    try:
        cmd = ["claude", "-p", prompt, "--output-format", "text"]
        if dosya_yazabilir:
            cmd.insert(1, "--dangerously-skip-permissions")
        result = sp.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=PROJE_DIZINI, encoding="utf-8", errors="replace"
        )
        return result.stdout.strip() if result.stdout else ""
    except sp.TimeoutExpired:
        log(f"  [AI] Claude zaman aşımı ({timeout}sn)", "warn")
    except FileNotFoundError:
        log(f"  [AI] Claude CLI bulunamadı!", "error")
    except Exception as e:
        log(f"  [AI] Claude hatası: {e}", "error")
    return ""


def _ai_sut_implementasyon_iste(ilac_adi, etkin_madde, rapor_kodu, mesaj_metni=""):
    """SUT kuralı tespit edilemeyen ilaç için Claude AI ile:
    1. Kategori belirle → DB'ye kaydet → runtime eşleştirme
    2. Mevcut kategoride kontrol fonksiyonu yoksa → sut_kontrolleri.py'ye kod yaz
    Arka plan thread'de çalışır, taramayı bloklamaz.
    """
    import threading

    # Aynı ilaç için tekrar sorma
    key = f"{ilac_adi}:{etkin_madde}"
    if key in _ai_istenen_ilaclar:
        return
    _ai_istenen_ilaclar.add(key)

    log(f"  [AI] SUT analizi başlıyor: {ilac_adi} ({etkin_madde})", "warn")

    def ai_thread():
        # ══════ AŞAMA 1: KATEGORİ BELİRLE ══════
        kategoriler = (
            "KOMBINE_ANTIHIPERTANSIF, DIYABET_DPP4_SGLT2, KLOPIDOGREL, STATIN, FIBRAT, "
            "YOAK, IVABRADIN, EPLERENON, RANOLAZIN, PSIKIYATRI, SOLUNUM, ONKOLOJI, NOROLOJI, "
            "GOZ, ANTIVIRAL, GIS, RECETE_TURU_KIRMIZI, RECETE_TURU_YESIL, TRIMETAZIDIN, "
            "DMAH, KADIN_HORMON, ANTIBIYOTIK_FLOROKINOLON, RAPORSUZ_BILGILENDIRME, "
            "MONO_ANTIHIPERTANSIF, POTASYUM_SITRAT, GENEL_RAPORLU"
        )

        prompt1 = (
            f"Türkiye SGK SUT mevzuatına göre bu ilacın SUT kategorisini belirle.\n"
            f"İlaç: {ilac_adi}\n"
            f"Etkin Madde: {etkin_madde or 'BİLİNMİYOR'}\n"
            f"Rapor Kodu: {rapor_kodu or 'yok'}\n"
            f"Mesaj: {(mesaj_metni or 'yok')[:200]}\n\n"
            f"KRİTİK KURAL: Etkin madde BİLİNMİYOR ise KESİNLİKLE TAHMİN YAPMA!\n"
            f"İlaç adından etkin madde tahmin etme — yanlış sonuç verir.\n"
            f"Etkin madde bilinmiyorsa KATEGORI: GENEL_RAPORLU yaz ve ETKIN_MADDE: BILINMIYOR yaz.\n"
            f"Sadece etkin madde kesin olarak biliniyorsa kategori belirle.\n\n"
            f"Önce ilacabak.com'dan ilacın etkin maddesini doğrula, sonra kategori belirle.\n\n"
            f"Mevcut kategoriler:\n{kategoriler}\n\n"
            f"SADECE şu formatta cevap ver, başka bir şey yazma:\n"
            f"KATEGORI: <kategori_kodu>\n"
            f"ETKIN_MADDE: <etkin madde adı büyük harf>\n"
            f"ACIKLAMA: <kısa açıklama>\n\n"
            f"Eğer mevcut kategorilerden hiçbiri uymuyorsa KATEGORI: GENEL_RAPORLU yaz.\n"
            f"Eğer raporsuz verilebilen bir ilaç ise KATEGORI: RAPORSUZ_BILGILENDIRME yaz."
        )

        cikti = _ai_claude_calistir(prompt1, timeout=60)
        if not cikti:
            log(f"  [AI] Aşama 1 başarısız ({ilac_adi})", "warn")
            return

        # Parse et
        kategori = None
        ai_etkin = None
        aciklama = ""
        for satir in cikti.split("\n"):
            satir = satir.strip()
            if satir.startswith("KATEGORI:"):
                kategori = satir.split(":", 1)[1].strip()
            elif satir.startswith("ETKIN_MADDE:"):
                ai_etkin = satir.split(":", 1)[1].strip()
            elif satir.startswith("ACIKLAMA:"):
                aciklama = satir.split(":", 1)[1].strip()

        if not kategori:
            log(f"  [AI] Kategori parse edilemedi: {cikti[:100]}", "warn")
            return

        log(f"  [AI] Kategori: {ilac_adi} → {kategori} ({aciklama})", "ok")

        # DB'ye kaydet
        try:
            from kontrol_kurallari import get_ogrenilen_ilaclar
            ogrenilen = get_ogrenilen_ilaclar()
            ogrenilen.ilac_kaydet(
                ilac_adi, etkin_madde=ai_etkin or etkin_madde,
                farmakolojik_grup=kategori, rapor_kodu=rapor_kodu
            )
        except Exception:
            pass

        # Runtime sözlüklere ekle
        try:
            from recete_kontrol import sut_kontrolleri
            ilac_kisa = ilac_adi.strip().upper().split()[0] if ilac_adi else ""
            if ilac_kisa and len(ilac_kisa) >= 3:
                sut_kontrolleri.ILAC_ADI_KATEGORI[ilac_kisa] = kategori
            if ai_etkin:
                sut_kontrolleri.ETKIN_MADDE_KATEGORI[ai_etkin.upper()] = kategori
        except Exception:
            pass

        # ══════ AŞAMA 2: KONTROL FONKSİYONU — YENİ YAZ VEYA MEVCUT GENİŞLET ══════
        try:
            from recete_kontrol import sut_kontrolleri
            fonk_var = kategori in sut_kontrolleri.KATEGORI_KONTROL_FONKSIYONU
        except Exception:
            fonk_var = False

        if fonk_var:
            log(f"  [AI] Kontrol fonksiyonu mevcut: {kategori} - genişletiliyor...", "info")
            _ai_kod_yaz(kategori, ilac_adi, ai_etkin or etkin_madde, rapor_kodu,
                         mesaj_metni, aciklama, guncelle=True)
        else:
            log(f"  [AI] Kontrol fonksiyonu YOK: {kategori} - yeni yazılıyor...", "warn")
            _ai_kod_yaz(kategori, ilac_adi, ai_etkin or etkin_madde, rapor_kodu,
                         mesaj_metni, aciklama, guncelle=False)

        # Kuyruğa kaydet
        try:
            kuyruk = []
            if os.path.exists(AI_IMPL_DOSYA):
                with open(AI_IMPL_DOSYA, "r", encoding="utf-8") as f:
                    kuyruk = json.load(f)
            kuyruk.append({
                "ilac_adi": ilac_adi, "etkin_madde": ai_etkin or etkin_madde,
                "rapor_kodu": rapor_kodu, "tarih": datetime.now().isoformat(),
                "durum": "tamamlandi", "kategori": kategori, "aciklama": aciklama,
                "kod_yazildi": not fonk_var
            })
            with open(AI_IMPL_DOSYA, "w", encoding="utf-8") as f:
                json.dump(kuyruk, f, indent=2, ensure_ascii=False)
        except:
            pass

    threading.Thread(target=ai_thread, daemon=True).start()


def _ai_kod_yaz(kategori, ilac_adi, etkin_madde, rapor_kodu, mesaj_metni, aciklama, guncelle=False):
    """Claude'a sut_kontrolleri.py'ye kontrol fonksiyonu yazdır veya mevcut olanı genişlet.
    --dangerously-skip-permissions ile çalışır, sadece sut_kontrolleri.py'ye dokunur.
    """
    sut_dosya = os.path.join(PROJE_DIZINI, "recete_kontrol", "sut_kontrolleri.py")

    # Mevcut fonksiyon kodunu oku (güncelleme için)
    mevcut_fonk_kodu = ""
    if guncelle:
        try:
            with open(sut_dosya, "r", encoding="utf-8") as f:
                icerik = f.read()
            # "def kontrol_xxx(" ile başlayan fonksiyonu bul
            fonk_adi = f"kontrol_{kategori.lower()}"
            import re as _re
            match = _re.search(
                rf'(def {fonk_adi}\(.*?\n(?:(?:    .*|)\n)*)',
                icerik
            )
            if match:
                mevcut_fonk_kodu = match.group(1)
        except Exception:
            pass

    if guncelle and mevcut_fonk_kodu:
        gorev = (
            f"Bu dosyada MEVCUT kontrol fonksiyonunu GENİŞLET ve İYİLEŞTİR.\n"
            f"Mevcut fonksiyon basit bir keyword kontrolü yapıyor. SUT mevzuatının\n"
            f"TÜM kurallarını kapsayacak şekilde genişlet.\n\n"
            f"MEVCUT FONKSİYON:\n```python\n{mevcut_fonk_kodu}```\n\n"
            f"GENİŞLETME TALİMATLARI:\n"
            f"- Mevcut fonksiyonu SİL ve yerine detaylı versiyonunu yaz\n"
            f"- SUT mevzuatındaki TÜM kuralları kontrol et:\n"
            f"  * Hangi uzman yazabilir?\n"
            f"  * Rapor süresi ne kadar?\n"
            f"  * Doz kısıtlamaları var mı?\n"
            f"  * Kombinasyon kısıtlamaları var mı?\n"
            f"  * İlk reçete/devam reçete farkı var mı?\n"
            f"  * Raporsuz yazılabilir mi?\n"
            f"- Her kural için ayrı kontrol yap ve detaylı mesaj döndür\n"
        )
    else:
        gorev = (
            f"Bu dosyada YENİ bir SUT kontrol fonksiyonu implemente et.\n\n"
            f"YAPILACAKLAR:\n"
            f"1. İnternetten (ilacabak.com, SGK SUT) bu ilacın SUT kuralını araştır\n"
            f"2. recete_kontrol/sut_kontrolleri.py dosyasına:\n"
            f"   a) ETKIN_MADDE_KATEGORI sözlüğüne '{etkin_madde}': '{kategori}' ekle\n"
            f"   b) def kontrol_{kategori.lower()}(ilac_sonuc) fonksiyonu yaz\n"
            f"   c) KATEGORI_KONTROL_FONKSIYONU sözlüğüne '{kategori}': kontrol_{kategori.lower()} ekle\n"
            f"   d) KATEGORI_ISIMLERI sözlüğüne açıklayıcı isim ekle\n"
        )

    prompt = (
        f"Proje dizini: {PROJE_DIZINI}\n"
        f"Dosya: recete_kontrol/sut_kontrolleri.py\n\n"
        f"{gorev}\n"
        f"İlaç: {ilac_adi}\n"
        f"Etkin Madde: {etkin_madde}\n"
        f"Rapor Kodu: {rapor_kodu or 'yok'}\n"
        f"Mesaj örneği: {(mesaj_metni or 'yok')[:300]}\n"
        f"Kategori kodu: {kategori}\n"
        f"Açıklama: {aciklama}\n\n"
        f"Kontrol fonksiyonu şablonu:\n"
        f"```python\n"
        f"def kontrol_{kategori.lower()}(ilac_sonuc: Dict) -> KontrolRaporu:\n"
        f"    metin = _tum_metinleri_birlesir(ilac_sonuc)\n"
        f"    rapor_kodu = ilac_sonuc.get('rapor_kodu', '')\n"
        f"    if not metin and not rapor_kodu:\n"
        f"        return KontrolRaporu(KontrolSonucu.KONTROL_EDILEMEDI, 'Rapor/mesaj metni yok')\n"
        f"    # SUT kuralına göre DETAYLI kontrol...\n"
        f"    # _turkce_ara(metin, 'aranan ibare') kullan (Türkçe karakter güvenli)\n"
        f"    return KontrolRaporu(KontrolSonucu.UYGUN, 'Detaylı açıklama')\n"
        f"```\n\n"
        f"YARDIMCI FONKSİYONLAR:\n"
        f"- _turkce_ara(metin, aranan) → bool: İ/i/ı fark etmez\n"
        f"- _tum_metinleri_birlesir(ilac_sonuc) → str: Tüm metin kaynakları\n"
        f"- KontrolSonucu.UYGUN / UYGUN_DEGIL / KONTROL_EDILEMEDI\n"
        f"- KontrolRaporu(sonuc, mesaj, detaylar={{}}, uyari='')\n\n"
        f"KRİTİK KURALLAR:\n"
        f"- SADECE recete_kontrol/sut_kontrolleri.py dosyasını düzenle\n"
        f"- Mevcut DİĞER fonksiyonları BOZMA\n"
        f"- Medula verileri değiştirme YASAK\n"
        f"- DB'ye INSERT/UPDATE/DELETE YASAK\n"
    )

    log(f"  [AI] Claude kod yazıyor: {kategori}...", "info")
    cikti = _ai_claude_calistir(prompt, timeout=300, dosya_yazabilir=True)
    if cikti:
        log(f"  [AI] Kod yazma tamamlandı: {kategori} ({len(cikti)} kr)", "ok")
        # Modülü yeniden yükle (yeni fonksiyonlar runtime'da aktif olsun)
        try:
            import importlib
            from recete_kontrol import sut_kontrolleri
            importlib.reload(sut_kontrolleri)
            log(f"  [AI] sut_kontrolleri modülü yeniden yüklendi", "info")
        except Exception as e:
            log(f"  [AI] Modül yeniden yükleme hatası: {e}", "warn")
    else:
        log(f"  [AI] Kod yazma başarısız: {kategori}", "warn")
RAPOR_JSON = os.path.join(PROJE_DIZINI, "tarama_rapor.json")


def _recete_sorgu_ile_git(medula, recete_no):
    """Reçete Sorgu sayfasından belirli bir reçeteye git.
    Önce ana sayfaya dön (menü görünür olsun) → Reçete Sorgu → No yaz → Sorgula
    Returns: True başarılı, False başarısız
    """
    log(f"  Reçete Sorgu ile {recete_no}'ya gidiliyor...", "info")

    # webBrowser1 focus
    try:
        for c in medula.children():
            try:
                if c.element_info.automation_id == "webBrowser1":
                    c.set_focus()
                    break
            except:
                pass
    except:
        pass
    time.sleep(0.3)

    # Önce menü görünür mü kontrol et
    menu_var = element_bul(medula, "form1:menuHtmlCommandExButton51")
    if not menu_var:
        # Menü yok - Giriş butonuyla ana sayfaya dön
        log("  Menü görünmüyor, Giriş butonuyla ana sayfaya dönülüyor...", "info")
        element_tikla(medula, "btnMedulayaGirisYap", "click")
        time.sleep(5)
        menu_var = element_bul(medula, "form1:menuHtmlCommandExButton51")

    if not menu_var:
        log("  Reçete Sorgu menüsü bulunamadı", "warn")
        return False

    # 1. Reçete Sorgu menüsüne tıkla
    if not element_tikla(medula, "form1:menuHtmlCommandExButton51"):
        log("  Reçete Sorgu tıklanamadı", "warn")
        return False

    # Sayfa yüklenene kadar bekle (text2 textbox görünene kadar)
    for i in range(10):
        time.sleep(1)
        if element_bul(medula, "form1:text2"):
            break
    else:
        log("  Reçete Sorgu sayfası yüklenemedi", "warn")
        return False

    # 2. Reçete numarasını yaz
    txt_elem = element_bul(medula, "form1:text2")
    if not txt_elem:
        log("  Reçete No textbox bulunamadı", "warn")
        return False

    try:
        txt_elem.click_input()
        time.sleep(0.2)
        import pyautogui
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.typewrite(recete_no, interval=0.03)
        log(f"  Reçete No yazıldı: {recete_no}", "info")
    except Exception as e:
        log(f"  Reçete No yazılamadı: {e}", "warn")
        return False

    time.sleep(0.5)

    # 3. Sorgula butonuna bas
    if not element_tikla(medula, "form1:buttonReceteNoSorgula"):
        log("  Sorgula butonu bulunamadı", "warn")
        return False

    log("  Sorgula tıklandı, reçete açılıyor...", "info")

    # 4. Reçete sayfasının yüklenmesini bekle
    for i in range(10):
        time.sleep(1)
        if element_bul(medula, "f:tbl1"):
            rno = recete_no_oku(medula)
            log(f"  Reçete açıldı: {rno}", "ok")
            return True

    log("  Reçete açılamadı", "warn")
    return False


def _son_recete_kaydet(grup, recete_no, sira=0):
    """Son kontrol edilen reçete no'yu JSON'a kaydet"""
    try:
        durum = {}
        if os.path.exists(DURUM_DOSYASI):
            with open(DURUM_DOSYASI, "r", encoding="utf-8") as f:
                durum = json.load(f)
        if grup not in durum:
            durum[grup] = {"son_recete": "", "toplam_kontrol": 0, "son_kontrol_tarihi": None}
        durum[grup]["son_recete"] = recete_no
        durum[grup]["toplam_kontrol"] = durum[grup].get("toplam_kontrol", 0) + 1
        durum[grup]["son_kontrol_tarihi"] = datetime.now().isoformat()
        with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(durum, f, indent=2, ensure_ascii=False)
        # stdout'a da yaz (GUI combobox + durum güncellemesi için)
        print(f"[SON_RECETE] {grup}:{recete_no}:{sira}", flush=True)
    except:
        pass


def _son_recete_al(grup):
    """Kaldığı yerden devam için son reçete no'yu oku"""
    try:
        if os.path.exists(DURUM_DOSYASI):
            with open(DURUM_DOSYASI, "r", encoding="utf-8") as f:
                durum = json.load(f)
            return durum.get(grup, {}).get("son_recete", "")
    except:
        pass
    return ""

RAPOR_SUTUNLAR = [
    ("Reçete No", 12),
    ("Reçete Türü", 12),
    ("İlaç Adı", 40),
    ("Etkin Madde", 25),
    ("Rapor Kodu", 10),
    ("Msj", 5),
    ("Renkli Reçete", 14),
    ("Rapor Kontrol", 14),
    ("SUT Kontrol", 12),
    ("Sonuç", 10),
    ("Açıklama", 50),
]

def rapor_kaydet(satirlar, grup):
    """Raporu JSON + Excel olarak kaydet"""
    if not satirlar:
        log("Rapor verisi yok, kayıt atlanıyor", "warn")
        return

    # 1. JSON kaydet (GUI tablo için)
    try:
        with open(RAPOR_JSON, "w", encoding="utf-8") as f:
            json.dump({"grup": grup, "tarih": datetime.now().isoformat(),
                       "satirlar": satirlar}, f, ensure_ascii=False, indent=2)
        log(f"Rapor JSON kaydedildi: {RAPOR_JSON}", "ok")
    except Exception as e:
        log(f"JSON kayıt hatası: {e}", "error")

    # 2. Excel kaydet
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = Workbook()
        ws = wb.active
        ws.title = f"{grup} Grubu Kontrol"

        # Stiller
        baslik_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        baslik_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        recete_fill = PatternFill(start_color="E8EAF6", end_color="E8EAF6", fill_type="solid")
        uygun_fill = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
        sorun_fill = PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid")
        uyari_fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
        yeni_fill = PatternFill(start_color="B3E5FC", end_color="B3E5FC", fill_type="solid")
        ince_border = Border(
            left=Side(style="thin", color="BDBDBD"),
            right=Side(style="thin", color="BDBDBD"),
            top=Side(style="thin", color="BDBDBD"),
            bottom=Side(style="thin", color="BDBDBD")
        )

        # Başlık satırı
        for col_idx, (baslik, genislik) in enumerate(RAPOR_SUTUNLAR, 1):
            cell = ws.cell(row=1, column=col_idx, value=baslik)
            cell.font = baslik_font
            cell.fill = baslik_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = ince_border
            ws.column_dimensions[cell.column_letter].width = genislik

        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:K{len(satirlar) + 1}"

        # Veri satırları
        onceki_recete = None
        for row_idx, satir in enumerate(satirlar, 2):
            recete_no = satir.get("recete_no", "")
            yeni_recete = recete_no != onceki_recete
            onceki_recete = recete_no

            degerler = [
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
            ]

            for col_idx, deger in enumerate(degerler, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=deger)
                cell.font = Font(name="Segoe UI", size=10)
                cell.border = ince_border
                cell.alignment = Alignment(vertical="center", wrap_text=True)

                # Reçete satırı arka plan
                if yeni_recete and col_idx <= 2:
                    cell.fill = recete_fill
                    cell.font = Font(name="Segoe UI", size=10, bold=True)

            # Kontrol sütunlarını renklendir (7=Renkli, 8=Rapor, 9=SUT, 10=Sonuç)
            sonuc = satir.get("sonuc", "")
            for col in [7, 8, 9]:
                cell = ws.cell(row=row_idx, column=col)
                val = cell.value or "-"
                if val == "Uygun":
                    cell.fill = uygun_fill
                elif val == "Uygun Değil":
                    cell.fill = sorun_fill
                elif val == "Uyarı":
                    cell.fill = uyari_fill
                elif val == "Yeni":
                    cell.fill = yeni_fill

            # Sonuç sütunu
            sonuc_cell = ws.cell(row=row_idx, column=10)
            if sonuc == "OK":
                sonuc_cell.fill = uygun_fill
            elif sonuc == "SORUN":
                sonuc_cell.fill = sorun_fill
                sonuc_cell.font = Font(name="Segoe UI", size=10, bold=True, color="B71C1C")
            elif sonuc == "UYARI":
                sonuc_cell.fill = uyari_fill
            elif sonuc == "YENİ":
                sonuc_cell.fill = yeni_fill

        # Kaydet
        masaustu = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
        tarih = datetime.now().strftime("%Y%m%d_%H%M")
        excel_dosya = os.path.join(masaustu, f"Kontrol_Raporu_{grup}_{tarih}.xlsx")
        wb.save(excel_dosya)
        log(f"Excel rapor kaydedildi: {excel_dosya}", "ok")

    except Exception as e:
        log(f"Excel rapor hatası: {e}", "error")


# ========== ANA TARAMA ==========
def tara(grup="A", donem_offset=0, bastan_basla=False, kontrol_edilmisleri_atla=False,
         acik_receteden=False, goto_recete_no=None):
    stop_temizle()

    log(f"{'='*50}", "header")
    log(f"REÇETE TARAMA - {grup} Grubu (offset: {donem_offset})", "header")
    log(f"Durdurma: Escape tuşu veya Durdur butonu", "info")
    log(f"{'='*50}", "header")

    # Medula bul
    medula = medula_bul()
    if not medula:
        log("MEDULA penceresi bulunamadı!", "error")
        return

    # Oturum kontrol
    medula = oturum_kontrol_ve_baglan(medula)
    if not medula:
        return

    log("Medula bağlı ve oturum aktif", "ok")

    if durduruldu_mu():
        log("DURDURULDU", "warn")
        return

    # Renkli reçete listesini yükle
    renkli_liste_yukle()

    # === BAŞLANGIÇ NOKTASI BELİRLE ===
    son_kayitli = _son_recete_al(grup)

    # "Kontrol edilmişleri atla" seçeneği: DB'den kontrol edilmiş reçeteleri al
    _kontrol_edilmis = set()
    if kontrol_edilmisleri_atla:
        try:
            _tmp_conn, _tmp_cur = db_baglanti()
            _tmp_cur.execute(
                "SELECT DISTINCT recete_no FROM kontrol_sonuclari WHERE grup = ?", (grup,))
            _kontrol_edilmis = {row[0] for row in _tmp_cur.fetchall()}
            _tmp_conn.close()
            if _kontrol_edilmis:
                log(f"DB'de {len(_kontrol_edilmis)} kontrol edilmiş reçete var - bunlar atlanacak", "info")
        except Exception:
            pass

    # === BAŞLANGIÇ MODU ===
    if acik_receteden:
        # Ekranda açık olan reçeteden başla (navigasyon yapma)
        if element_bul(medula, "f:tbl1"):
            mevcut = recete_no_oku(medula)
            log(f"Açık reçeteden başlanıyor: {mevcut}", "ok")
        else:
            log("Ekranda açık reçete yok! Navigasyon yapılıyor...", "warn")
            if not medula_navigasyon(medula, grup, donem_offset):
                return
    elif goto_recete_no:
        # Belirli bir reçeteye git (combobox'tan seçildi)
        log(f"Reçete {goto_recete_no}'ya gidiliyor...", "info")
        if _recete_sorgu_ile_git(medula, goto_recete_no):
            log(f"Reçete {goto_recete_no}'dan devam ediliyor", "ok")
        else:
            log(f"Reçete {goto_recete_no}'ya gidilemedi, navigasyon yapılıyor", "warn")
            if not medula_navigasyon(medula, grup, donem_offset):
                return
    elif element_bul(medula, "f:tbl1") and not bastan_basla:
        log("Reçete sayfası zaten açık", "ok")
    else:
        if not medula_navigasyon(medula, grup, donem_offset):
            return

    conn, cur = db_baglanti()

    sayac = 0
    onceki_recete = None
    tekrar_sayaci = 0
    toplam_ilac = 0
    toplam_sorun = 0
    toplam_renkli_sorun = 0
    yeni_kural = 0
    rapor_satirlari = []  # Excel/GUI raporu için veri toplama

    while sayac < 300:
        # === STOP KONTROL ===
        if durduruldu_mu():
            log("", "header")
            log("TARAMA DURDURULDU (kullanıcı tarafından)", "warn")
            break

        # === SİSTEM HATASI KONTROL ===
        if sistem_dusmus_mu(medula):
            log("SİSTEM HATASI TESPİT EDİLDİ - Medula yeniden başlatılıyor...", "error")
            medula = medula_yeniden_baslat()
            if not medula:
                log("Medula yeniden başlatılamadı - tarama durduruluyor", "error")
                break
            # Navigasyonu tekrar yap
            if not medula_navigasyon(medula, grup, donem_offset):
                log("Navigasyon başarısız - tarama durduruluyor", "error")
                break
            # Son kaldığımız reçeteye dönmeye çalış
            log(f"Sistem hatası sonrası yeniden başlatıldı, tarama devam ediyor", "ok")
            continue

        # === GOTO KONTROL (GUI'den reçete seçildi mi?) ===
        goto_recete = goto_recete_kontrol()
        if goto_recete:
            log(f"GUI'den geri dönme isteği: {goto_recete}", "info")
            if _recete_sorgu_ile_git(medula, goto_recete):
                log(f"Reçete {goto_recete}'ya geri dönüldü", "ok")
                onceki_recete = None
                tekrar_sayaci = 0
            else:
                log(f"Reçete {goto_recete}'ya gidilemedi, devam ediliyor", "warn")

        sayac += 1

        recete_no = recete_no_oku(medula)

        # Tekrar kontrolü
        if recete_no == onceki_recete:
            tekrar_sayaci += 1
            if tekrar_sayaci >= 3:
                log(f"Reçete değişmiyor ({recete_no}) - tarama bitti", "info")
                break
            element_tikla(medula, "f:buttonSonraki")
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

        # Daha önce kontrol edilmiş reçeteyi atla (kaldığı yerden devam)
        if recete_no in _kontrol_edilmis:
            log(f"  {recete_no} zaten kontrol edilmiş - atlanıyor", "info")
            element_tikla(medula, "f:buttonSonraki")
            time.sleep(2)
            continue

        log(f"", "info")
        log(f"━━━ Reçete #{sayac}: {recete_no} ━━━", "header")

        # === ADIM 1: REÇETE TÜRÜ ===
        recete_turu = recete_turu_oku(medula)
        tur_bilgi = f"[{recete_turu}]" if recete_turu != "Normal" else "[Beyaz]"
        log(f"  Tür: {tur_bilgi}", "info")

        # === ADIM 2: RENKLİ REÇETE KONTROLÜ ===
        renkli_sonuc = "-"
        renkli_aciklama = ""
        if recete_turu != "Normal":
            sorun, mesaj = renkli_recete_kontrol(recete_no, recete_turu)
            renkli_sonuc = "Uygun Değil" if sorun else "Uygun"
            renkli_aciklama = mesaj
            if sorun:
                toplam_renkli_sorun += 1
                log(f"  {mesaj}", "sorun")
            else:
                log(f"  {mesaj}", "ok")

        # === ADIM 2B: UYARI KODLARI KONTROLÜ ===
        uyari_kodlari = uyari_kodlari_oku(medula)
        uk_sonuclar = []
        recete_teshisleri = []
        if uyari_kodlari:
            # Bypass kontrolü: uyarı kodu bazlı filtreleme
            try:
                from kontrol_kurallari import get_kontrol_ayarlari
                _uk_ayarlar = get_kontrol_ayarlari()
                filtreli_uk = []
                for uk in uyari_kodlari:
                    uk_kod = uk.get("kod", "") if isinstance(uk, dict) else str(uk)
                    uk_aciklama = uk.get("aciklama", "") if isinstance(uk, dict) else ""
                    if _uk_ayarlar.kontrol_aktif_mi("uyari_kodu", uyari_kodu=uk_kod):
                        filtreli_uk.append(uk)
                    else:
                        log(f"    [BYPASS] Uyarı kodu {uk_kod}: {uk_aciklama} → kontrol pasif (ayar)", "info")
                uyari_kodlari = filtreli_uk
            except Exception:
                pass

            if uyari_kodlari:
                recete_teshisleri = recete_teshisleri_oku(medula)
                log(f"  {len(uyari_kodlari)} uyarı kodu bulundu, teşhislerle eşleştiriliyor...", "info")
                # Ön kontrol: reçete teşhisleri ile
                uk_sonuclar = uyari_kodu_kontrol(uyari_kodlari, recete_teshisleri, [], [])
                for uks in uk_sonuclar:
                    if uks["durum"] == "UYGUN":
                        log(f"    [  OK ] Uyarı {uks['kod']}: {uks['aciklama']} (teşhiste eşleşti)", "ok")
                    else:
                        log(f"    [SUT ] Uyarı {uks['kod']}: {uks['aciklama']} → rapor bilgisiyle kontrol edilecek", "warn")

        # === ADIM 3: İLAÇ TABLOSU KONTROLÜ (Her reçetede yapılır) ===
        ilaclar = ilaclari_oku(medula)

        if not ilaclar:
            log("  İlaç okunamadı, sonrakine geçiliyor", "warn")
            rapor_satirlari.append({
                "recete_no": recete_no, "recete_turu": recete_turu,
                "ilac_adi": "", "etkin_madde": "", "rapor_kodu": "", "msj": "",
                "renkli_kontrol": renkli_sonuc, "rapor_kontrol": "-",
                "sut_kontrol": "-", "sonuc": "UYARI", "aciklama": "İlaç okunamadı"
            })
        else:
            log(f"  {len(ilaclar)} ilaç bulundu - detaylı kontrol başlıyor:", "info")

            for idx, ilac in enumerate(ilaclar):
                toplam_ilac += 1

                # Yeni etkin madde ise DB'ye kaydet
                etkin = ilac.get("etkin_madde", "")
                kural = db_kural_bul(cur, etkin)
                if not kural and etkin:
                    rapor_kodu = ilac.get("rapor_kodu", "")
                    raporlu = 1 if rapor_kodu else 0
                    tip = "rapor_kontrolu" if raporlu else "raporsuz_verilebilir"
                    if db_kaydet(cur, conn, etkin, ilac.get("sgk_kodu", ""),
                                rapor_kodu, raporlu, tip,
                                f"Otomatik: {ilac['ilac_adi']}"):
                        yeni_kural += 1
                    log(f"    [YENİ] {ilac['ilac_adi'][:40]} -> DB'ye eklendi", "yeni")

                # 4 durumlu karar ağacı (AA/BB/CC/DD)
                satir = ilac_detayli_kontrol(
                    medula, cur, conn, grup, recete_no, recete_turu,
                    ilac, idx, renkli_sonuc
                )

                # Renkli kontrol bilgisini ilk ilaca ekle
                if idx == 0:
                    satir["renkli_kontrol"] = renkli_sonuc

                rapor_satirlari.append(satir)

                # Sonuç sayacı
                if satir["sonuc"] == "UYGUNSUZ":
                    toplam_sorun += 1

            # === ADIM 4: UYARI KODLARI - RAPOR BİLGİSİYLE YENİDEN KONTROL ===
            # İlaç kontrollerinde okunan rapor verilerini topla
            uygunsuz_uk = [uks for uks in uk_sonuclar if uks["durum"] == "UYGUNSUZ"]
            if uygunsuz_uk:
                rapor_aciklamalari = []
                rapor_tanilari = []
                for s in rapor_satirlari:
                    rv = s.get("_rapor_verisi", {})
                    if rv:
                        rapor_aciklamalari.extend(rv.get("aciklamalar", []))
                        rapor_tanilari.extend(rv.get("tanilar", []))
                        rapor_tanilari.extend(rv.get("icd_kodlari", []))

                if rapor_aciklamalari or rapor_tanilari:
                    log(f"  {len(uygunsuz_uk)} uyarı kodu rapor bilgisiyle yeniden kontrol ediliyor...", "info")
                    uk_yeni = uyari_kodu_kontrol(
                        uygunsuz_uk, recete_teshisleri, rapor_aciklamalari, rapor_tanilari
                    )
                    for uks in uk_yeni:
                        if uks["durum"] == "UYGUN":
                            log(f"    [  OK ] Uyarı {uks['kod']}: {uks['aciklama']} (raporda eşleşti)", "ok")
                        else:
                            log(f"    [SORUN] Uyarı {uks['kod']}: {uks['aciklama']} (raporda bulunamadı)", "sorun")
                            toplam_sorun += 1
                else:
                    # Rapor verisi yok - uygunsuz olarak kalsın
                    for uks in uygunsuz_uk:
                        log(f"    [SORUN] Uyarı {uks['kod']}: {uks['aciklama']} (rapor verisi okunamadı)", "sorun")
                        toplam_sorun += 1

            # _rapor_verisi iç kullanım alanını temizle (Excel'e yazılmasın)
            for s in rapor_satirlari:
                s.pop("_rapor_verisi", None)

        # Sayfa durumu kontrolü - İlaç Bilgi penceresi açık kalmış olabilir
        if element_bul(medula, "form1:buttonKapat"):
            log("  İlaç Bilgi penceresi açık kalmış, kapatılıyor...", "warn")
            element_tikla(medula, "form1:buttonKapat")
            time.sleep(1)

        # Son kontrol edilen reçeteyi kaydet (kaldığı yerden devam için)
        if recete_no:
            _son_recete_kaydet(grup, recete_no, sayac)

        # Sonraki reçete
        if not element_tikla(medula, "f:buttonSonraki"):
            # Kurtarma: Escape + tekrar dene
            pyautogui.press("escape")
            time.sleep(1)
            if not element_tikla(medula, "f:buttonSonraki"):
                log("Sonraki butonu bulunamadı - tarama bitti", "info")
                break

        # Sayfa yüklenene kadar bekle (ilaç tablosu görünecek)
        for bekle in range(4):
            time.sleep(0.5)
            if durduruldu_mu():
                break
            if element_bul(medula, "f:tbl1:0:t6"):  # İlk ilaç adı hücresi
                break
        time.sleep(0.5)

    # Özet
    try:
        cur.execute("SELECT COUNT(*) FROM etkin_madde_kurallari")
        toplam_db = cur.fetchone()[0]
    except:
        toplam_db = "?"

    # Kontrol sonuçları özeti (DB'den)
    toplam_uygun = 0
    toplam_uygunsuz = 0
    toplam_gecildi = 0
    try:
        cur.execute("SELECT genel_sonuc, COUNT(*) FROM kontrol_sonuclari WHERE grup = ? GROUP BY genel_sonuc", (grup,))
        for row in cur.fetchall():
            if row[0] == "UYGUN":
                toplam_uygun = row[1]
            elif row[0] == "UYGUNSUZ":
                toplam_uygunsuz = row[1]
            elif row[0] == "GECİLDİ":
                toplam_gecildi = row[1]
    except:
        pass

    conn.close()

    log(f"", "header")
    log(f"{'='*50}", "header")
    log(f"TARAMA TAMAMLANDI", "header")
    log(f"  Taranan reçete    : {sayac}", "info")
    log(f"  Toplam ilaç       : {toplam_ilac}", "info")
    log(f"  Uygun             : {toplam_uygun}", "ok")
    log(f"  Uygunsuz          : {toplam_uygunsuz}", "error" if toplam_uygunsuz > 0 else "info")
    log(f"  Geçildi           : {toplam_gecildi}", "info")
    log(f"  Sorunlu ilaç      : {toplam_sorun}", "error" if toplam_sorun > 0 else "info")
    log(f"  Renkli reçete sor.: {toplam_renkli_sorun}", "error" if toplam_renkli_sorun > 0 else "info")
    log(f"  Yeni öğrenilen    : {yeni_kural}", "info")
    log(f"  DB toplam kural   : {toplam_db}", "info")
    log(f"{'='*50}", "header")

    # Rapor kaydet (JSON + Excel)
    rapor_kaydet(rapor_satirlari, grup)

    stop_temizle()


if __name__ == "__main__":
    grup = sys.argv[1] if len(sys.argv) > 1 else "A"
    donem_offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    bastan = "--bastan" in sys.argv
    acik_receteden = "--acik" in sys.argv
    kontrol_edilmisleri_atla = "--atla" in sys.argv
    goto_recete_no = None
    if "--goto" in sys.argv:
        idx = sys.argv.index("--goto")
        if idx + 1 < len(sys.argv):
            goto_recete_no = sys.argv[idx + 1]
    tara(grup=grup, donem_offset=donem_offset, bastan_basla=bastan,
         kontrol_edilmisleri_atla=kontrol_edilmisleri_atla,
         acik_receteden=acik_receteden, goto_recete_no=goto_recete_no)
