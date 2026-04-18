"""
MEDULA Kullanılan İlaç Listesi Okuyucu
--------------------------------------
BotanikEOS içinde gömülü MEDULA web sayfasındaki (ReceteIslem2.jsp)
"Kullanılan İlaç Listesi" tablosunu okur.

SALT OKUMA: Hiçbir form kaydedilmez, hiçbir buton tıklanmaz.

Tablo yapısı (HTML'den):
    <TABLE id="form1:tableExKisiIlacList">
      <TR id="TR_parentof_form1:tableExKisiIlacList:{N}:rowAction2">
        text14: Reçete No
        text15: İlaç Adı
        text10: Reçete Tar.
        text21: İlaç Alım Tar.
        text13: Verilebileceği Tarih
        text18: Adet
        text17: İlaç Kullanımı
        text26: Rap. Teşhisi / Rap. Tak. No   ← RAPOR KODU
        (UK sütunu — SPAN id yok)
        Yazılabilir Tarih (TD — SPAN id yok): ya tarih ya da
                                              "Yazdırma günü gelmiştir"
        Stk (TD — SPAN id yok)

"Günü gelmiş ilaç" = Yazılabilir Tarih hücresi tam olarak
"Yazdırma günü gelmiştir" metnini içerir.

Mesaja alınacak ilaç = günü gelmiş VE rapor kodu (text26) dolu olanlar.
"""

import logging
import re
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

TABLO_ID = "form1:tableExKisiIlacList"
GUNU_GELDI_METNI = "Yazdırma günü gelmiştir"
_ROW_AID_PAT = re.compile(r"^form1:tableExKisiIlacList:(\d+):(\w+)$")


def _medula_hwnd_hizli():
    """MEDULA HWND'sini win32gui ile hızlıca bul. Dialog'ları dışlar."""
    try:
        import win32gui
    except Exception:
        return None
    hedef_hwnd = None

    def _enum(hwnd, _):
        nonlocal hedef_hwnd
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd) or ""
            cls = win32gui.GetClassName(hwnd) or ""
            if cls.startswith("#32770"):
                return True
            if not cls.startswith("WindowsForms"):
                return True
            if "MEDULA" in title and hedef_hwnd is None:
                hedef_hwnd = hwnd
            elif "BotanikEOS" in title and "(T)" in title and hedef_hwnd is None:
                hedef_hwnd = hwnd
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum, None)
    except Exception:
        pass
    return hedef_hwnd


def medula_bul():
    """MEDULA (BotanikEOS) ana penceresini pywinauto wrapper olarak döndür.

    Worker thread'lerde UIA COM problemi olabilir — try/except ile
    Desktop(backend="uia") çağrısını koru, başarısız olursa fallback.
    """
    hwnd = _medula_hwnd_hizli()
    if not hwnd:
        # Son çare: recete_tarama.medula_bul (UIA tarama — yavaş)
        try:
            from recete_tarama import medula_bul as _mb
            win = _mb()
            if win is not None:
                return win
        except Exception as e:
            logger.debug(f"recete_tarama.medula_bul hatası: {e}")
        return None

    # pywinauto wrapper'a dönüştürmeye çalış (caller .set_focus() vb. çağırabilir)
    try:
        from pywinauto import Desktop
        return Desktop(backend="uia").window(handle=hwnd)
    except Exception as e:
        logger.warning(f"Desktop(uia) wrap başarısız ({e}) — HWND-only wrapper")

    # Fallback: minimal HWND wrapper — sadece .handle attribute'u
    class _HwndProxy:
        def __init__(self, h):
            self.handle = h
        def set_focus(self):
            try:
                import win32gui
                win32gui.SetForegroundWindow(self.handle)
            except Exception:
                pass
        def window_text(self):
            try:
                import win32gui
                return win32gui.GetWindowText(self.handle) or ""
            except Exception:
                return ""
        def descendants(self, *a, **kw):
            return []  # UIA yok — boş döner
    return _HwndProxy(hwnd)


def _elem_metni(elem) -> str:
    """Bir element için metin temsilini döndür."""
    if elem is None:
        return ""
    try:
        t = (elem.window_text() or "").strip()
        if t:
            return t
    except Exception:
        pass
    try:
        info = elem.legacy_properties()
        if isinstance(info, dict):
            val = info.get("Value") or info.get("Name") or ""
            if val:
                return str(val).strip()
    except Exception:
        pass
    return ""


def _elem_value(elem) -> str:
    """HTMLElement.innerText / value değerini döndür."""
    if elem is None:
        return ""
    for attr in ("innerText", "value"):
        try:
            v = getattr(elem, attr, None)
            if v:
                return str(v).strip()
        except Exception:
            continue
    return ""


def ilaclari_oku(medula=None) -> List[Dict]:
    """MEDULA açık ReceteIslem2.jsp sayfasındaki 'Kullanılan İlaç Listesi'
    tablosundan GÜNÜ GELMİŞ + RAPOR KODU DOLU satırları döndür.

    HTML DOM üzerinden (COM) okur — UIA'dan 100+ kat hızlı.

    Dönüş (her kayıt):
        {
          "urun_adi": str, "recete_no": str, "recete_tarihi": str,
          "ilac_alim_tarihi": str, "verilebilecegi_tarih": str,
          "adet": str, "ilac_kullanimi": str, "rapor_kodu": str,
          "satir_no": int,
        }
    """
    try:
        from medula_html_dom import html_doc_bul
    except Exception as e:
        logger.error(f"medula_html_dom import hatası: {e}")
        return []

    doc = html_doc_bul()
    if doc is None:
        logger.warning("HTMLDocument alınamadı")
        return []

    sonuc: List[Dict] = []
    toplam_satir = 0
    gunu_gelen = 0
    rapor_dolu = 0

    # IE8 COM'da doc.all koleksiyonu en güvenli tarama yolu.
    # N = 0,1,2,... artır; text15 yoksa döngü biter.
    # (500 satırdan fazlası beklenmez — güvenlik için 500'de durdur.)
    for satir_no in range(500):
        try:
            aid_ilac = f"form1:tableExKisiIlacList:{satir_no}:text15"
            urun_elem = doc.getElementById(aid_ilac)
        except Exception:
            urun_elem = None
        if urun_elem is None:
            break  # Daha fazla satır yok
        toplam_satir += 1

        urun_adi = _elem_value(urun_elem)
        if not urun_adi:
            continue

        # Rapor kodu
        rapor_kodu = ""
        try:
            e = doc.getElementById(
                f"form1:tableExKisiIlacList:{satir_no}:text26"
            )
            rapor_kodu = _elem_value(e)
        except Exception:
            pass
        if rapor_kodu:
            rapor_dolu += 1

        # Yazılabilir hücresi — SPAN-id yok, TR'nin 11. TD'si (0-based: 10)
        # olarak parent TR'den oku. Daha güvenilir yol: parent TR innerText'inde
        # "Yazdırma günü gelmiştir" geçiyor mu?
        gunu_geldi = False
        try:
            # urun_elem'in parent TR'sini bul
            parent = urun_elem
            for _ in range(5):
                if parent is None:
                    break
                tag = ""
                try:
                    tag = (getattr(parent, "tagName", "") or "").upper()
                except Exception:
                    pass
                if tag == "TR":
                    break
                try:
                    parent = parent.parentElement
                except Exception:
                    parent = None
            if parent is not None:
                try:
                    ic = parent.innerText or ""
                except Exception:
                    ic = ""
                if GUNU_GELDI_METNI in ic:
                    gunu_geldi = True
        except Exception:
            pass

        if gunu_geldi:
            gunu_gelen += 1

        # Filtre: günü gelmiş VE rapor kodu dolu olmalı
        if not gunu_geldi:
            continue
        if not rapor_kodu:
            continue

        # Diğer sütunları topla
        def _g(idx):
            try:
                e = doc.getElementById(
                    f"form1:tableExKisiIlacList:{satir_no}:{idx}"
                )
                return _elem_value(e)
            except Exception:
                return ""

        sonuc.append({
            "urun_adi": urun_adi,
            "recete_no": _g("text14"),
            "recete_tarihi": _g("text10"),
            "ilac_alim_tarihi": _g("text21"),
            "verilebilecegi_tarih": _g("text13"),
            "adet": _g("text18"),
            "ilac_kullanimi": _g("text17"),
            "rapor_kodu": rapor_kodu,
            "satir_no": satir_no,
        })

    logger.info(
        f"Kullanılan İlaç Listesi (DOM): toplam {toplam_satir} satır, "
        f"{gunu_gelen} günü gelmiş, {rapor_dolu} rapor kodu dolu, "
        f"{len(sonuc)} ilaç döndürüldü"
    )
    return sonuc


def hasta_adi_oku(medula=None) -> str:
    """Kullanılan İlaç Listesi sayfasında 'Adı / Soyadı' alanından hasta
    adını oku (HTML DOM üzerinden). Bulunamazsa boş string.

    form1:text7 = Ad,  form1:text6 = Soyad
    """
    try:
        from medula_html_dom import html_doc_bul
    except Exception as e:
        logger.debug(f"medula_html_dom import hatası: {e}")
        return ""
    doc = html_doc_bul()
    if doc is None:
        return ""
    ad = ""
    soyad = ""
    try:
        e = doc.getElementById("form1:text7")
        if e is not None:
            ad = (getattr(e, "innerText", "") or "").strip()
    except Exception:
        pass
    try:
        e = doc.getElementById("form1:text6")
        if e is not None:
            soyad = (getattr(e, "innerText", "") or "").strip()
    except Exception:
        pass
    return f"{ad} {soyad}".strip()


def hasta_tc_oku_maskeli(medula=None) -> str:
    """Kullanılan İlaç Listesi sayfasında 'T.C. Kimlik Numarası' alanından
    maskeli TC'yi oku. Örn: '28159453****'.

    form1:text18 = Maskeli TC
    """
    try:
        from medula_html_dom import html_doc_bul
    except Exception:
        return ""
    doc = html_doc_bul()
    if doc is None:
        return ""
    try:
        e = doc.getElementById("form1:text18")
        if e is not None:
            return (getattr(e, "innerText", "") or "").strip()
    except Exception:
        pass
    return ""


def kullanilan_ilac_sayfasi_mi() -> bool:
    """MEDULA'da şu an 'Kullanılan İlaç Listesi' görünümü açık mı?"""
    try:
        from medula_html_dom import html_doc_bul
        doc = html_doc_bul()
        if doc is None:
            return False
        body = (doc.body.innerHTML or "") if doc.body else ""
        return "Kullanılan İlaç Listesi" in body
    except Exception:
        return False


def hasta_dogrula(kuyruk_hasta_adi: str, kuyruk_tc: str) -> tuple:
    """MEDULA'daki sayfa kuyruk kaydıyla aynı hastaya mı ait kontrol et.

    Eşleşme kuralı:
      - Ad + Soyad birebir (büyük/küçük duyarsız)
      - VEYA TC'nin ilk 8 hanesi birebir (MEDULA maskeli: 12345678****)

    Dönüş: (eslesme: bool, mesaj: str, pencere_hasta: str, pencere_tc: str)
    """
    pencere_adi = hasta_adi_oku()
    pencere_tc_mask = hasta_tc_oku_maskeli()

    if not pencere_adi and not pencere_tc_mask:
        # Sayfa muhtemelen Kullanılan İlaç Listesi değil
        return False, (
            "MEDULA'da 'Kullanılan İlaç Listesi' sayfası açık değil. "
            "Önce 💊 İlaç Listesi Aç butonuna basıp doğru sayfayı açın."
        ), "", ""

    # Ad/soyad eşleşmesi
    ad_eslesti = False
    if pencere_adi and kuyruk_hasta_adi:
        if pencere_adi.strip().lower() == kuyruk_hasta_adi.strip().lower():
            ad_eslesti = True

    # TC ilk 8 hane eşleşmesi
    tc_eslesti = False
    if pencere_tc_mask and kuyruk_tc:
        # Maskeden rakamları al
        pencere_ilk = "".join(ch for ch in pencere_tc_mask if ch.isdigit())[:8]
        kuyruk_ilk = "".join(ch for ch in kuyruk_tc if ch.isdigit())[:8]
        if pencere_ilk and kuyruk_ilk and pencere_ilk == kuyruk_ilk:
            tc_eslesti = True

    if ad_eslesti or tc_eslesti:
        hangi = []
        if ad_eslesti:
            hangi.append("ad/soyad")
        if tc_eslesti:
            hangi.append("TC ilk 8")
        return (
            True,
            f"✓ Eşleşti ({', '.join(hangi)})",
            pencere_adi, pencere_tc_mask,
        )
    return (
        False,
        f"UYUMSUZLUK: MEDULA = '{pencere_adi}' ({pencere_tc_mask}), "
        f"kuyruk = '{kuyruk_hasta_adi}' ({kuyruk_tc})",
        pencere_adi, pencere_tc_mask,
    )
