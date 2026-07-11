# -*- coding: utf-8 -*-
"""
E-Reçete Çözücü — Medula Otomasyon Katmanı

KartsizEreceteSorgu.jsp ekranında, verilen bir e-reçete / takip numarasını
ilgili textbox'a yazar, Sorgula butonuna basar ve sonucu tespit eder.

🚨 GÜVENLİK (CLAUDE.md §1): Bu modül Medula'da SADECE OKUMA/NAVİGASYON yapar.
   - Yazılan tek alan: e-reçete-no / takip-no SORGU textbox'ı ve (opsiyonel) TC.
     Bunlar reçete/rapor VERİSİ değil, sorgu (arama) alanlarıdır.
   - Reçete kaydetme, ilaç ekleme/silme, form verisi değiştirme YOK.
   - Koordinat tıklama YOK — sadece DOM .click() / dispatchEvent (JS).

Element ID'leri (UIElementInspector arşivinden, 2026-07-10):
   TC Kimlik textbox      : form1:textSmartDeger
   E-Reçete No textbox    : form1:text4          (maxLength=7)
   E-Reçete Sorgula       : form1:buttonSorgula
   Takip No textbox       : form1:text9          (maxLength=7)
   Takip Sorgula          : form1:buttonSorgula2
   "kayıt bulunamadı"     : SPAN.outputText (id yok) → gövde metninde ara
   Hasta ismi (başarı)    : form1:text39
   Sonuç satırı hücresi   : form1:tableExERecete:0:text25
"""

import logging
import time

logger = logging.getLogger(__name__)

# ── Element ID sabitleri ───────────────────────────────────────────────────
ID_TC = "form1:textSmartDeger"
ID_ERECETE_TEXT = "form1:text4"
ID_ERECETE_SORGULA = "form1:buttonSorgula"
ID_TAKIP_TEXT = "form1:text9"
ID_TAKIP_SORGULA = "form1:buttonSorgula2"
ID_HASTA_ISMI = "form1:text39"
ID_SONUC_HUCRE = "form1:tableExERecete:0:text25"

# Sonuç durumları
BULUNDU = "BULUNDU"
BULUNAMADI = "BULUNAMADI"
BELIRSIZ = "BELIRSIZ"
HATA = "HATA"

# "Bulunamadı" tespiti için gövdede aranan ibare (küçük harf)
_BULUNAMADI_IBARE = "bulunamad"   # "bulunamadı" / "bulunamadi"


def _medula_exe_baslat():
    """medula_settings'teki exe yolundan BotanikMedula'yı başlat. Başarı: bool."""
    import os
    import subprocess
    try:
        from medula_settings import get_medula_settings
        exe = get_medula_settings().get("medula_exe_path", "")
    except Exception:
        exe = r"C:\BotanikEczane\BotanikMedula.exe"
    if not exe or not os.path.exists(exe):
        logger.warning(f"Medula exe yolu geçersiz: {exe!r}")
        return False
    try:
        subprocess.Popen([exe])
        logger.info(f"Medula başlatıldı: {exe}")
        return True
    except Exception as e:
        logger.error(f"Medula başlatılamadı: {e}")
        return False


def _medula_kapat():
    """SADECE BotanikMedula.exe'yi kapat (BotanikEczane.exe'ye dokunma)."""
    import subprocess
    try:
        subprocess.run(["taskkill", "/F", "/IM", "BotanikMedula.exe"],
                       capture_output=True)
        logger.info("BotanikMedula.exe kapatıldı (yeniden açmak için).")
    except Exception as e:
        logger.debug(f"BotanikMedula kapatma: {e}")


def _hwnd_bekle(sure_sn: float):
    """Medula penceresi görünene kadar bekle (poll). hwnd veya None."""
    import medula_html_dom as mhd
    son = time.monotonic() + sure_sn
    while time.monotonic() < son:
        h = mhd._medula_hwnd()
        if h:
            return h
        time.sleep(0.5)
    return None


def medula_hazirla(cb=None, max_deneme: int = 2):
    """Medula'yı e-Reçete Sorgu ekranına hazır hale getir (best-effort).

    Adımlar (kullanıcı isteği): pencere yoksa AÇ → oturum düşmüşse GİRİŞ'e bas
    (şifre YAZILMAZ, sadece butona basılır; wrapper kayıtlı kimlikle girer) →
    e-Reçete Sorgu ekranını AÇ. Hâlâ hazır değilse (hata/takılma) BotanikMedula
    kapatılıp yeniden açılır. Şifre girişi YAPILMAZ — giriş ekranı manuel şifre
    isterse kullanıcıya bırakılır.

    cb(mesaj): ilerleme bildirimi. Dönüş: (hazir: bool, mesaj: str).
    """
    def _log(m):
        if cb:
            try:
                cb(m)
            except Exception:
                pass

    try:
        import medula_html_dom as mhd
    except Exception as e:
        return False, f"medula_html_dom yok: {e}"

    for deneme in range(1, max_deneme + 1):
        # 1) Pencere var mı? Yoksa başlat.
        hwnd = mhd._medula_hwnd()
        if not hwnd:
            _log("Medula açık değil — başlatılıyor…")
            if not _medula_exe_baslat():
                return False, ("Medula başlatılamadı — exe yolu ayarlı mı? "
                               "(Kurulum sihirbazı)")
            hwnd = _hwnd_bekle(45)
            if not hwnd:
                return False, "Medula açıldı ama pencere bulunamadı (45sn)."
            time.sleep(2)

        # 2) Zaten sorgu ekranında mı?
        uygun, _m = sorgu_ekraninda_mi()
        if uygun:
            return True, "Medula hazır."

        # 3) Oturum düşmüş olabilir → Giriş butonuna bas (şifre yazmadan)
        _log("Giriş kontrol ediliyor…")
        try:
            mhd.giris_tikla(hwnd)     # login ekranı değilse no-op
        except Exception:
            pass
        time.sleep(6)

        # 4) e-Reçete Sorgu menüsünü aç
        _log("e-Reçete Sorgu açılıyor…")
        try:
            mhd.erecete_sorgu_tikla(hwnd)
        except Exception:
            pass
        time.sleep(3)

        uygun, _m = sorgu_ekraninda_mi()
        if uygun:
            return True, "Medula hazır."

        # 5) Hâlâ değil → kapat-yeniden aç (son deneme hariç)
        if deneme < max_deneme:
            _log("Hazırlanamadı — Medula kapatılıp yeniden açılıyor…")
            _medula_kapat()
            time.sleep(3)

    return False, ("Medula e-Reçete Sorgu ekranı hazırlanamadı. Giriş ekranı "
                   "şifre istiyorsa elle giriş yapın, sonra tekrar deneyin.")


def giris_alani_konumu(hwnd=None):
    """Medula E-Reçete Sorgu ekranındaki TC + E-Reçete textbox bölgesinin
    EKRAN dikdörtgenini döndürür: (x, y, genislik, yukseklik) piksel.

    getBoundingClientRect (viewport-göreli) + IE_Server client ekran orijini.
    Bulunamazsa None (Medula açık değil / farklı sayfa).
    """
    try:
        import medula_html_dom as mhd
        import win32gui
    except Exception:
        return None
    if hwnd is None:
        hwnd = mhd._medula_hwnd()
    if not hwnd:
        return None
    ie = mhd._ie_server_hwnd(hwnd)
    if not ie:
        return None
    doc = mhd.html_doc_bul(hwnd)
    if doc is None:
        return None
    try:
        tc = doc.getElementById(ID_TC)
        er = doc.getElementById(ID_ERECETE_TEXT)
        if tc is None:
            return None

        def _rect(el):
            r = el.getBoundingClientRect()
            return (float(r.left), float(r.top), float(r.right), float(r.bottom))

        l, t, rr, b = _rect(tc)
        if er is not None:
            el2, et2, er2, eb2 = _rect(er)
            l = min(l, el2)
            t = min(t, et2)
            rr = max(rr, er2)
            b = max(b, eb2)
        ox, oy = win32gui.ClientToScreen(ie, (0, 0))
        return (int(ox + l), int(oy + t), int(rr - l), int(b - t))
    except Exception as e:
        logger.debug(f"giris_alani_konumu hata: {e}")
        return None


def prefix_tablosu_oku(hwnd=None):
    """Medula E-Reçete Sorgu ekranındaki prefix tablolarını okur.

    Ekranda 'ERxNo 2P3 …' (yeşil) ve 'TakipNo 59X …' (mavi) satırları, o
    dönemin e-reçete / takip numara başlangıçlarını tarih sırasıyla (en yeni
    üstte) listeler. Bunları okuyup döndürür.

    Dönüş: {'erecete': [prefix,...], 'takip': [prefix,...]} (ilk = en güncel).
    Okunamazsa boş listeler.
    """
    import re
    sonuc = {"erecete": [], "takip": []}
    try:
        import medula_html_dom as mhd
    except Exception:
        return sonuc
    if hwnd is None:
        hwnd = mhd._medula_hwnd()
    if not hwnd:
        return sonuc
    doc = mhd.html_doc_bul(hwnd)
    if doc is None:
        return sonuc
    try:
        metin = doc.body.innerText or ""
    except Exception:
        try:
            metin = doc.body.innerHTML or ""
        except Exception:
            metin = ""
    if not metin:
        return sonuc
    # 'ERxNo' / 'TakipNo' etiketini takip eden 2-4 karakterlik alfanümerik prefix
    for m in re.findall(r"ERxNo[\s:]*([0-9A-Za-z]{2,4})", metin):
        p = m.strip().upper()
        if p and p not in sonuc["erecete"]:
            sonuc["erecete"].append(p)
    for m in re.findall(r"TakipNo[\s:]*([0-9A-Za-z]{2,4})", metin):
        p = m.strip().upper()
        if p and p not in sonuc["takip"]:
            sonuc["takip"].append(p)
    return sonuc


def canli_alan_yaz(mode, numara=None, tc=None, hwnd=None):
    """Canlı aktarım: TC ve/veya numarayı ilgili Medula alanlarına YAZ
    (tıklamadan, hızlı, best-effort). mode: 'erecete'|'takip'.
    numara/tc None ise o alana dokunulmaz. Dönüş: yazıldı mı (bool)."""
    try:
        import medula_html_dom as mhd
    except Exception:
        return False
    if hwnd is None:
        hwnd = mhd._medula_hwnd()
    if not hwnd:
        return False
    doc = mhd.html_doc_bul(hwnd)
    if doc is None:
        return False
    yazildi = False
    if tc is not None:
        if _alan_yaz(doc, ID_TC, tc):
            yazildi = True
    if numara is not None:
        tid = ID_TAKIP_TEXT if mode == "takip" else ID_ERECETE_TEXT
        if _alan_yaz(doc, tid, numara):
            yazildi = True
    return yazildi


def sorgula_gonder(mode, hwnd=None):
    """İlgili alanın Sorgula butonuna bas (tek sorgu — sonuç beklemez).
    mode: 'erecete'|'takip'. Dönüş: tıklandı mı (bool)."""
    try:
        import medula_html_dom as mhd
    except Exception:
        return False
    if hwnd is None:
        hwnd = mhd._medula_hwnd()
    if not hwnd:
        return False
    doc = mhd.html_doc_bul(hwnd)
    if doc is None:
        return False
    sid = ID_TAKIP_SORGULA if mode == "takip" else ID_ERECETE_SORGULA
    return _sorgula_tikla(doc, sid)


def numara_tipi_belirle(numara: str) -> str:
    """Yazılan numaranın 'takip' mi 'erecete' mi olduğunu tahmin eder.

    Heuristik: e-reçete numaraları alfanümeriktir (harf içerir), takip
    numaraları genelde tamamen rakamdır. Harf varsa → 'erecete',
    tamamı rakam → 'takip'. Boş/belirsiz → 'erecete' (varsayılan).
    """
    s = "".join(c for c in (numara or "") if c.isalnum())
    if not s:
        return "erecete"
    return "takip" if s.isdigit() else "erecete"


def _dom():
    """medula_html_dom modülünden doc + hwnd döndürür (yoksa (None, None))."""
    try:
        import medula_html_dom as mhd
    except Exception as e:
        logger.error(f"medula_html_dom import edilemedi: {e}")
        return None, None, None
    hwnd = mhd._medula_hwnd()
    if not hwnd:
        return mhd, None, None
    doc = mhd.html_doc_bul(hwnd)
    return mhd, hwnd, doc


def _pencere_one(hwnd):
    """Medula penceresini öne getir (varsa). Hata olursa sessiz geç."""
    if not hwnd:
        return
    try:
        from pencere_yerlesim import _pencereyi_one_getir  # type: ignore
        _pencereyi_one_getir(hwnd)
        return
    except Exception:
        pass
    try:
        import recete_kontrol.medula_rapor_tarayici as mrt  # type: ignore
        mrt._pencereyi_one_getir(hwnd)
    except Exception:
        pass


def sorgu_ekraninda_mi():
    """KartsizEreceteSorgu ekranı açık mı? (e-reçete VE takip textbox'ları var mı)

    Dönüş: (uygun: bool, mesaj: str)
    """
    mhd, hwnd, doc = _dom()
    if mhd is None:
        return False, "medula_html_dom modülü yok."
    if not hwnd:
        return False, "Medula penceresi bulunamadı — Medula açık mı?"
    if doc is None:
        return False, "Medula'da web sayfası (HTMLDocument) alınamadı."
    try:
        t4 = doc.getElementById(ID_ERECETE_TEXT)
        t9 = doc.getElementById(ID_TAKIP_TEXT)
    except Exception as e:
        return False, f"DOM erişim hatası: {e}"
    if t4 is None and t9 is None:
        return False, ("E-Reçete Sorgu ekranı açık değil. Medula'da "
                       "'e-Reçete Sorgu' menüsünü açın.")
    return True, "E-Reçete Sorgu ekranı hazır."


def _alan_yaz(doc, html_id, deger):
    """textbox'ı temizle + değer yaz. Başarı: bool."""
    try:
        elem = doc.getElementById(html_id)
        if elem is None:
            return False
        try:
            elem.value = ""
        except Exception:
            pass
        elem.value = str(deger)
        return True
    except Exception as e:
        logger.warning(f"_alan_yaz({html_id}) hata: {e}")
        return False


def _sorgula_tikla(doc, html_id):
    """Sorgula butonuna bas. Önce DOM .click(), olmazsa execScript. Başarı: bool."""
    try:
        btn = doc.getElementById(html_id)
        if btn is not None:
            try:
                btn.click()
                return True
            except Exception as e:
                logger.debug(f"{html_id} .click() hata, execScript denenecek: {e}")
    except Exception:
        pass
    # execScript fallback
    try:
        js = (
            "(function(){var b=document.getElementById('%s');"
            "if(b){b.click();}})();" % html_id
        )
        try:
            doc.parentWindow.execScript(js, "JavaScript")
        except Exception:
            doc.execScript(js, "JavaScript")
        return True
    except Exception as e:
        logger.warning(f"_sorgula_tikla({html_id}) execScript hata: {e}")
        return False


def _sonuc_oku(doc):
    """Mevcut DOM'da sonucu sınıflandır:
        BULUNDU    — hasta ismi dolu veya sonuç satırı var
        BULUNAMADI — gövdede 'bulunamadı' ibaresi var
        None       — henüz belli değil (yükleniyor olabilir)
    """
    try:
        # 1) Başarı: hasta ismi span dolu mu?
        ismi = doc.getElementById(ID_HASTA_ISMI)
        if ismi is not None:
            try:
                txt = (ismi.innerText or "").strip()
            except Exception:
                txt = ""
            if txt:
                return BULUNDU
        # 2) Başarı: sonuç satırı hücresi var mı?
        hucre = doc.getElementById(ID_SONUC_HUCRE)
        if hucre is not None:
            return BULUNDU
    except Exception:
        pass
    # 3) Başarısız: gövde metninde "bulunamadı"
    try:
        body = doc.body
        metin = ""
        try:
            metin = (body.innerText or "")
        except Exception:
            metin = (body.innerHTML or "")
        if _BULUNAMADI_IBARE in metin.lower():
            return BULUNAMADI
    except Exception:
        pass
    return None


def _hazir_mi(doc):
    try:
        rs = str(getattr(doc, "readyState", "complete") or "complete").lower()
        return rs == "complete"
    except Exception:
        return True


def tek_dene(deger, mode="erecete", tc=None, hwnd=None,
             ilk_bekleme=0.4, zaman_asimi=8.0):
    """Tek bir numara dener.

    mode: "erecete" | "takip"
    tc  : verilirse her denemeden önce TC alanına yazılır (None → dokunma)
    Dönüş: (durum, mesaj)  durum ∈ {BULUNDU, BULUNAMADI, BELIRSIZ, HATA}
    """
    try:
        import medula_html_dom as mhd
    except Exception as e:
        return HATA, f"medula_html_dom yok: {e}"

    if hwnd is None:
        hwnd = mhd._medula_hwnd()
    if not hwnd:
        return HATA, "Medula penceresi yok."

    doc = mhd.html_doc_bul(hwnd)
    if doc is None:
        return HATA, "HTMLDocument alınamadı."

    if mode == "takip":
        text_id, sorgula_id = ID_TAKIP_TEXT, ID_TAKIP_SORGULA
    else:
        text_id, sorgula_id = ID_ERECETE_TEXT, ID_ERECETE_SORGULA

    # (opsiyonel) TC yaz
    if tc:
        _alan_yaz(doc, ID_TC, tc)

    # Numara yaz
    if not _alan_yaz(doc, text_id, deger):
        return HATA, f"'{deger}' yazılamadı ({text_id} yok — doğru ekran mı?)."

    # Sorgula
    if not _sorgula_tikla(doc, sorgula_id):
        return HATA, "Sorgula tıklanamadı."

    # Postback'in başlaması için kısa bekleme
    time.sleep(ilk_bekleme)

    # Sonuç için polling: taze doc al, hazır + sonuç belli olana dek bekle
    son = time.monotonic() + zaman_asimi
    while time.monotonic() < son:
        d = mhd.html_doc_bul(hwnd)
        if d is not None and _hazir_mi(d):
            durum = _sonuc_oku(d)
            if durum is not None:
                return durum, f"{deger} → {durum}"
        time.sleep(0.15)

    return BELIRSIZ, f"{deger} → sonuç {zaman_asimi:.0f}sn'de belirlenemedi."


def sonuc_satirini_ac(hwnd=None, bekle=2.5):
    """Başarılı sorgudan sonra sonuç satırına tıklayıp reçete detayına girer.

    IBM HxClient tableEx satırları addEventListener ile click handler taşır;
    IE COM .click() bunları tetiklemez. dispatchEvent + initMouseEvent gerçek
    MouseEvent üretir. Bilinen hücre id'sinden TR'ye tırmanıp tıklar.
    Dönüş: (basarili: bool, mesaj: str)
    """
    try:
        import medula_html_dom as mhd
    except Exception as e:
        return False, f"medula_html_dom yok: {e}"
    if hwnd is None:
        hwnd = mhd._medula_hwnd()
    if not hwnd:
        return False, "Medula penceresi yok."
    _pencere_one(hwnd)
    time.sleep(0.3)
    doc = mhd.html_doc_bul(hwnd)
    if doc is None:
        return False, "HTMLDocument alınamadı."

    js = (
        "(function(){"
        "var el=document.getElementById('form1:tableExERecete:0:rowActionReceteSec');"
        "if(!el){el=document.getElementById('form1:tableExERecete:0:text25');}"
        "if(!el){var a=document.getElementsByTagName('*');"
        "for(var i=0;i<a.length;i++){var id=a[i].id||'';"
        "if(id.indexOf('tableExERecete:0')>=0){el=a[i];break;}}}"
        "if(!el){return;}"
        "var tr=el;while(tr&&tr.tagName&&tr.tagName.toUpperCase()!=='TR'){tr=tr.parentNode;}"
        "var t=tr||el;var ev;"
        "if(document.createEvent){ev=document.createEvent('MouseEvents');"
        "ev.initMouseEvent('click',true,true,window,1,0,0,0,0,false,false,false,false,0,null);"
        "t.dispatchEvent(ev);}"
        "else if(document.createEventObject){ev=document.createEventObject();"
        "t.fireEvent('onclick',ev);}"
        "})();"
    )
    try:
        try:
            doc.parentWindow.execScript(js, "JavaScript")
        except Exception:
            doc.execScript(js, "JavaScript")
    except Exception as e:
        return False, f"Satır tıklama (execScript) hatası: {e}"
    time.sleep(bekle)
    return True, "Sonuç satırına tıklandı (reçete detayına giriliyor)."
