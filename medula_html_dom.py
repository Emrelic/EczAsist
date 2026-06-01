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


def _btnsonraki_tikla(medula_hwnd: int = None) -> bool:
    """MEDULA toolbar'ındaki WinForms 'Sonra >' butonuna tıkla.

    Yöntem: Win32 EnumChildWindows ile hwnd bul → pywinauto ile
    bu hwnd'ye attach et → click_input() ile gerçek mouse click gönder.

    Not: Eskiden SendMessage(BM_CLICK) kullanılıyordu ama WinForms
    butonu bazen BM_CLICK'e tepki vermiyor (mesaj alınıyor ama postback
    tetiklenmiyor). click_input() gerçek SendInput mouse event gönderiyor.
    """
    if medula_hwnd is None:
        medula_hwnd = _medula_hwnd()
    if not medula_hwnd:
        logger.warning("btnSonraki: MEDULA pencere handle'ı yok")
        return False

    # 1) Win32 EnumChildWindows ile buton hwnd'sini bul
    button_hwnd = None
    try:
        import win32gui
        bulunan = [None]

        def _enum(h, _):
            try:
                text = win32gui.GetWindowText(h) or ""
                cls = win32gui.GetClassName(h) or ""
                if "Sonra" in text and "WindowsForms" in cls:
                    bulunan[0] = h
                    return False
            except Exception:
                pass
            return True

        win32gui.EnumChildWindows(medula_hwnd, _enum, None)
        button_hwnd = bulunan[0]
        if button_hwnd and not win32gui.IsWindowEnabled(button_hwnd):
            logger.warning("btnSonraki disabled")
            return False
    except Exception as e:
        logger.debug(f"btnSonraki Win32 enum hatası: {e}")

    # 2) pywinauto ile gerçek mouse click
    try:
        from pywinauto import Application
    except ImportError:
        logger.error("pywinauto yok")
        return False

    try:
        app = Application(backend="uia").connect(handle=medula_hwnd, timeout=3)

        # Öncelik: Win32'de bulunan hwnd varsa direkt ona attach
        btn = None
        if button_hwnd:
            try:
                btn = app.window(handle=button_hwnd)
                if not btn.exists(timeout=1):
                    btn = None
            except Exception:
                btn = None

        # Fallback: auto_id / title ile ara
        if btn is None:
            win = app.window(handle=medula_hwnd)
            btn = win.child_window(auto_id="btnSonraki", control_type="Button")
            if not btn.exists(timeout=2):
                btn = win.child_window(title="Sonra >", control_type="Button")
            if not btn.exists(timeout=2):
                logger.warning("btnSonraki: element bulunamadı")
                return False

        # Gerçek mouse click (SendInput) — WinForms buton için en güvenilir
        try:
            btn.click_input()
            logger.info("btnSonraki click_input() başarılı")
            return True
        except Exception as e:
            logger.warning(f"click_input başarısız, invoke deneniyor: {e}")
            btn.invoke()
            logger.info("btnSonraki invoke() başarılı")
            return True
    except Exception as e:
        logger.warning(f"btnSonraki pywinauto: {type(e).__name__}: {e}")
        return False


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
    """TC yaz + İlaç Listesi aç akışı:

    A) "Kullanılan İlaç Listesi" sayfası AÇIK ise:
       1) form1:buttonGeriDon tıkla (reçeteye dön)
       2) btnSonraki (Sonra >) tıkla
       3) f:t18 textbox'ını temizle
       4) f:t18'e TC yaz
       5) f:buttonIlacListesi tıkla

    B) Reçete detay sayfası açık ise (kullanıcı isteği):
       2) VAR OLAN reçetede btnSonraki (Sonra >) tıkla — SONRA TC yaz
       3) f:t18 textbox'ını temizle
       4) f:t18'e TC yaz
       5) f:buttonIlacListesi tıkla

    Her iki akışta 'Sonra >' butonu pasif/bulunamadı ise (örn. listedeki
    son reçetedeyiz) mevcut reçeteye yapıştırmaya düşülür (fallback) —
    böylece buton her durumda iş görür.

    Dönüş: (basarili: bool, mesaj: str)
    """
    import time

    if not tc or len(tc) != 11 or not tc.isdigit():
        return False, f"Geçersiz TC: {tc!r}"

    doc = html_doc_bul(medula_hwnd)
    if doc is None:
        return False, "HTMLDocument alınamadı — MEDULA'da web sayfası açık mı?"

    def _f_t18_bekle(sure_sn: float):
        """Sayfa yüklenip f:t18 gelene kadar bekle. (doc, tc_input) döner."""
        deadline = time.monotonic() + sure_sn
        while time.monotonic() < deadline:
            d = html_doc_bul(medula_hwnd)
            if d is not None:
                try:
                    rs = str(getattr(d, "readyState", "complete") or "complete").lower()
                    if rs == "complete":
                        t = element_by_id(d, "f:t18")
                        if t is not None:
                            return d, t
                except Exception:
                    pass
            time.sleep(0.05)
        return None, None

    akis_log = []

    def _sonraki_ve_bekle():
        """btnSonraki ('Sonra >') tıkla, sonraki reçete sayfası
        (f:t18 + f:buttonIlacListesi) hazır olana dek bekle.

        Başarılı → (doc, tc_input). 'Sonra >' pasif/bulunamadı veya yeni
        sayfa 20sn'de yüklenmediyse → (None, None) — çağıran mevcut
        reçeteye yapıştırmaya düşer (fallback)."""
        if not _btnsonraki_tikla(medula_hwnd):
            return None, None
        time.sleep(0.3)  # WinForms postback'in başlaması için minimum
        # readyState=complete + f:t18 + f:buttonIlacListesi var olana dek
        # bekle. Koşul sağlanır sağlanmaz döner — 20s güvenlik timeout'u.
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            d = html_doc_bul(medula_hwnd)
            if d is not None:
                try:
                    rs = str(getattr(d, "readyState", "complete") or "complete").lower()
                    if rs == "complete":
                        t = element_by_id(d, "f:t18")
                        ilac = element_by_id(d, "f:buttonIlacListesi")
                        if t is not None and ilac is not None:
                            akis_log.append("Sonra")
                            return d, t
                except Exception:
                    pass
            time.sleep(0.05)
        return None, None

    # A) Kullanılan İlaç Listesi açıksa: Geri Dön → Sonra >
    if _kullanilan_ilac_sayfasi_mi(doc):
        # 1) Geri Dön
        geri = element_by_id(doc, "form1:buttonGeriDon")
        if geri is None:
            return False, "1) Geri Dön (form1:buttonGeriDon) bulunamadı."
        try:
            geri.click()
        except Exception as e:
            return False, f"1) Geri Dön tıklanamadı: {type(e).__name__}: {e}"
        akis_log.append("Geri")

        # Geri click'in postback başlatması için minimum bekleme
        time.sleep(0.3)

        # Reçete sayfası yüklensin — f:t18 görünene kadar polling
        doc, tc_input = _f_t18_bekle(20.0)
        if doc is None:
            return False, "1) Geri Dön sonrası sayfa 20sn'de yüklenmedi."

        # 2) Mevcut reçetede 'Sonra >' tıkla. Yeni reçete gelirse onu kullan;
        #    pasif/son reçete ise mevcut reçeteye yapıştırmaya düş (fallback).
        yeni_doc, yeni_tc = _sonraki_ve_bekle()
        if yeni_tc is not None:
            doc, tc_input = yeni_doc, yeni_tc
        else:
            akis_log.append("Sonra(atlandı)")
    else:
        # B) Reçete detay sayfası açık. Kullanıcı isteği: önce VAR OLAN
        #    reçetede 'Sonra >' tıkla, SONRA TC yapıştır. 'Sonra >' pasifse
        #    (örn. son reçete) mevcut reçeteye yapıştırmaya düş (fallback).
        tc_input = element_by_id(doc, "f:t18")
        if tc_input is None:
            return False, (
                "f:t18 (Reçete Sahibi T.C.) bulunamadı. MEDULA'da "
                "reçete detay sayfası (ReceteIslem2) açık olmalı."
            )
        yeni_doc, yeni_tc = _sonraki_ve_bekle()
        if yeni_tc is not None:
            doc, tc_input = yeni_doc, yeni_tc
        else:
            akis_log.append("Sonra(atlandı)")

    # 3) TC textbox temizle
    try:
        tc_input.value = ""
    except Exception as e:
        return False, f"3) TC temizlenemedi: {type(e).__name__}: {e}"
    akis_log.append("Temizle")

    # 4) Panodaki TC'yi yaz
    try:
        tc_input.value = tc
    except Exception as e:
        return False, f"4) TC yazılamadı: {type(e).__name__}: {e}"
    akis_log.append(f"TC={tc}")

    # 5) İlaç butonu
    ilac_btn = element_by_id(doc, "f:buttonIlacListesi")
    if ilac_btn is None:
        return False, "5) f:buttonIlacListesi butonu bulunamadı."
    try:
        ilac_btn.click()
    except Exception as e:
        return False, f"5) İlaç butonu tıklanamadı: {type(e).__name__}: {e}"
    akis_log.append("İlaç")

    return True, f"✓ {' → '.join(akis_log)}"
