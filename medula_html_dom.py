"""
MEDULA içindeki Internet Explorer_Server gömülü tarayıcının HTMLDocument
nesnesine COM üzerinden erişir. UIA descendants taraması yerine doğrudan
getElementById ile element bulur (çok daha hızlı: <100ms vs 20+ sn).

Kullanım:
    doc = html_doc_bul()   # veya html_doc_bul(hwnd)
    elem = doc.getElementById("f:t18")
    elem.value = "12345678901"
    btn = doc.getElementById("f:buttonIlacListesi")
    btn.click()
"""

import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

_user32 = ctypes.windll.user32
_oleacc = ctypes.windll.oleacc

# WM_HTML_GETOBJECT — IE gömülü tarayıcıdan HTMLDocument almak için
_WM_HTML_GETOBJECT = _user32.RegisterWindowMessageW("WM_HTML_GETOBJECT")

_user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_long),
]
_user32.SendMessageTimeoutW.restype = wintypes.LPARAM


def _ie_server_hwnd(parent_hwnd):
    """MEDULA'nın içindeki Internet Explorer_Server child HWND'sini döndür."""
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


def _medula_hwnd():
    """MEDULA ana penceresini bul."""
    try:
        from pencere_yerlesim import _medula_hwnd_bul
        return _medula_hwnd_bul()
    except Exception:
        return None


def _com_init():
    """Bu thread için COM'u başlat (zaten init edilmişse sessizce devam).
    Worker thread'lerinden COM çağrıları için gerekli."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        # Already initialized with different mode — OK
        pass


def html_doc_bul(medula_hwnd: int = None):
    """MEDULA'nın IE server'ındaki HTMLDocument'a COM proxy döndür.

    Her thread'de CoInitialize çağırır (tkinter worker thread'leri COM
    uninitialized başlar — bu olmazsa ObjectFromLresult fail eder).

    Dönüş: pywin32 IHTMLDocument2 proxy (getElementById, body vb.)
    Bulunamazsa None.
    """
    _com_init()  # thread-local COM init

    if medula_hwnd is None:
        medula_hwnd = _medula_hwnd()
    if not medula_hwnd:
        return None

    ie_hwnd = _ie_server_hwnd(medula_hwnd)
    if not ie_hwnd:
        logger.warning("Internet Explorer_Server child HWND bulunamadı")
        return None

    # Adım 1: IE_Server'a WM_HTML_GETOBJECT mesajı gönder
    lres = ctypes.c_long(0)
    rc = _user32.SendMessageTimeoutW(
        ie_hwnd, _WM_HTML_GETOBJECT, 0, 0, 0, 1000, ctypes.byref(lres),
    )
    if rc == 0 or lres.value == 0:
        logger.warning(f"WM_HTML_GETOBJECT başarısız (hwnd={ie_hwnd})")
        return None

    # Adım 2: LRESULT'tan IHTMLDocument2 COM interface'i al
    # IID_IHTMLDocument2 = {332C4425-26CB-11D0-B483-00C04FD90119}
    try:
        import pythoncom
        import win32com.client
    except ImportError as e:
        logger.error(f"pywin32 gerekli: {e}")
        return None

    import comtypes  # comtypes ile GUID oluştur
    IID_IHTMLDocument2 = comtypes.GUID("{332C4425-26CB-11D0-B483-00C04FD90119}")

    _oleacc.ObjectFromLresult.argtypes = [
        ctypes.c_long, ctypes.c_char_p, wintypes.WPARAM,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    _oleacc.ObjectFromLresult.restype = wintypes.LONG

    pdoc = ctypes.c_void_p()
    iid_bytes = bytes(IID_IHTMLDocument2)
    hr = _oleacc.ObjectFromLresult(
        lres.value, iid_bytes, 0, ctypes.byref(pdoc),
    )
    if hr != 0 or not pdoc.value:
        logger.error(f"ObjectFromLresult hatası hr={hr:#x}")
        return None

    # pdoc → pywin32 IDispatch wrapper
    try:
        idoc = pythoncom.ObjectFromAddress(pdoc.value, pythoncom.IID_IDispatch)
        doc = win32com.client.Dispatch(idoc)
        return doc
    except Exception as e:
        logger.error(f"ObjectFromAddress hatası: {e}")
        return None


def element_by_id(doc, html_id: str):
    """doc.getElementById(html_id) — pywin32 IDispatch üzerinden."""
    if doc is None:
        return None
    try:
        return doc.getElementById(html_id)
    except Exception as e:
        logger.error(f"getElementById({html_id}) hatası: {e}")
        return None


def _kullanilan_ilac_sayfasi_mi(doc) -> bool:
    """DOM'da 'Kullanılan İlaç Listesi' başlığı var mı?"""
    if doc is None:
        return False
    try:
        body = doc.body
        html = body.innerHTML or ""
        return "Kullanılan İlaç Listesi" in html
    except Exception:
        return False


def tc_yaz_ve_ilac_listesi_ac(tc: str, medula_hwnd: int = None) -> tuple:
    """En hızlı akış: HTML DOM üzerinden f:t18 değerini set et ve
    f:buttonIlacListesi'a click() gönder.

    Eğer şu an "Kullanılan İlaç Listesi" sayfası açıksa (kullanıcı önceden
    bir hastayı açmış), önce form1:buttonGeriDon butonuna basarak ReceteIslem2
    detay sayfasına dönülür, sayfa yenilenene kadar beklenir, sonra TC yazılır.

    Dönüş: (basarili: bool, mesaj: str)
    """
    import time

    if not tc or len(tc) != 11 or not tc.isdigit():
        return False, f"Geçersiz TC: {tc!r}"

    doc = html_doc_bul(medula_hwnd)
    if doc is None:
        return False, "HTMLDocument alınamadı — MEDULA'da web sayfası açık mı?"

    # Şu an Kullanılan İlaç Listesi sayfasındaysak önce Geri Dön
    if _kullanilan_ilac_sayfasi_mi(doc):
        logger.info("Kullanılan İlaç Listesi sayfasında — önce Geri Dön")
        geri = element_by_id(doc, "form1:buttonGeriDon")
        if geri is None:
            return False, (
                "Kullanılan İlaç Listesi sayfasındayız ama Geri Dön "
                "(form1:buttonGeriDon) bulunamadı."
            )
        try:
            geri.click()
        except Exception as e:
            return False, f"Geri Dön tıklanamadı: {type(e).__name__}: {e}"

        # Sayfa yeniden yüklensin diye bekle; f:t18 görünene kadar
        deadline = time.monotonic() + 5.0
        tc_input = None
        while time.monotonic() < deadline:
            time.sleep(0.2)
            doc = html_doc_bul(medula_hwnd)
            if doc is None:
                continue
            tc_input = element_by_id(doc, "f:t18")
            if tc_input is not None:
                break
        if tc_input is None:
            return False, (
                "Geri Dön sonrası f:t18 (Reçete Sahibi T.C.) 5 sn'de "
                "bulunamadı."
            )
    else:
        tc_input = element_by_id(doc, "f:t18")
        if tc_input is None:
            return False, (
                "f:t18 (Reçete Sahibi T.C.) bulunamadı.\n"
                "MEDULA'da bir reçete detay sayfası (ReceteIslem2) açık olmalı."
            )

    ilac_btn = element_by_id(doc, "f:buttonIlacListesi")
    if ilac_btn is None:
        return False, "f:buttonIlacListesi butonu bulunamadı."

    try:
        tc_input.value = tc
    except Exception as e:
        return False, f"TC yazılamadı: {type(e).__name__}: {e}"

    try:
        ilac_btn.click()
    except Exception as e:
        return False, f"Buton tıklanamadı: {type(e).__name__}: {e}"

    return True, f"✓ TC {tc} yazıldı, İlaç Listesi butonuna basıldı."
