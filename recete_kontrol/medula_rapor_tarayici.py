# -*- coding: utf-8 -*-
"""MEDULA Hasta Rapor Geçmişi Tarayıcı.

Bir hastanın MEDULA'daki tüm raporlarını (bitmiş + aktif) tek tek gezerek
yerel SQLite DB'ye (`hasta_rapor_gecmisi`) kaydeder. Hepatit/diyabet/KOAH
gibi kontrollerde 'başlangıç raporu var mı / kim verdi / hangi tarihte'
sorgusu için kullanılır.

CLAUDE.md uyumu:
  • Salt OKUMA + navigasyon. MEDULA verisinde DEĞİŞTİRME YOK.
  • Koordinat tıklama YASAK — element-bazlı pywinauto invoke()/click_input()
    veya MSHTML doc.getElementById().click() kullanılır. Tek istisna:
    Adım 11 (reçete listesi 1. satır) için element-relative başlık+30dp
    fallback (mutlak ekran koordinatı değil; başlık elementinin rect'ine
    göre relatif).

20-adımlı navigasyon (caption envanteri 2026-05-18):
   1. BotanikMedula.exe başlat (subprocess)
   2. Login penceresi: 'BotanikEOS 2.1.227.0 (T)'
   3. cmbKullanicilar combobox → 'botan'
   4. botan seçildi (item caption gereksiz, click_input + send_keys)
   5. txtSifre edit → '152634'
   6. btnGirisYap.invoke()
   7. MEDULA ana sayfa: 'MEDULA 2.1.227.0 botan (T)'
   8. Sol menü Reçete Listesi → form1:menuHtmlCommandExButton31
   9. B grubu → td[veri="4"]
   9b. Sorgula → form1:buttonSonlandirilmamisReceteler
  10. Reçete listesi tablosu başlık 'Sıra' (verification)
  11. 1. reçete satırı (3-katmanlı fallback: DOM scan → pattern guess →
      'Sıra' başlık + 30dp altı element-relative click_input)
  12. f:t18 → hastanın TC'si (panodan Ctrl+V)
  13. TC temizle: Ctrl+A → Del → Ctrl+V (caption gereksiz)
  14. f:buttonRaporListesi (Rapor)
  15. form1:buttonBitmisRaporlariDaGoster (Bitmiş Raporları da Göster)
  16. Raporlar tablosu başlık 'Rapor Takip No' (verification)
  17. Satırları oku: form1:tableExRaporTeshisList:N:textXX
      • text14 = rapor takip no
      • text15 = rapor tipi
      • text96 = rapor kodu + tanı (örn. '14.01 - Hepatit B Enfeksiyon(B18.1)')
      • text97 = bitiş tarihi
      • text98 = başlangıç tarihi
  18. Detay sayfası 'Rapor Görme' (sadece istenen kategoride raporlar için)
  19. form1:buttonGeriDon (rapor detay → liste)
  20. form1:buttonGeriDon (rapor listesi → reçete detay)
"""
from __future__ import annotations

import enum
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from recete_kontrol.hasta_rapor_gecmisi_db import (
    KATEGORI_ICD_PREFIX, RaporKaydi, kaydet, mevcut_rapor_takipleri,
    rapor_kodu_metnini_parcala, sema_olustur,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# 1. SABİTLER — caption envanteri (2026-05-18)
# ═════════════════════════════════════════════════════════════════════════

MEDULA_EXE_PATH = r'C:\BotanikEczane\BotanikMedula.exe'

# WinForms (login)
LOGIN_TITLE                = 'BotanikEOS'    # contains (fallback)
LOGIN_AUTOMATION_ID        = 'SifreSorForm'  # kanıtlı — recete_tarama.py:770
ANASAYFA_TITLE             = 'MEDULA'        # contains
COMBO_KULLANICI            = 'cmbKullanicilar'
EDIT_SIFRE                 = 'txtSifre'
BUTTON_GIRIS               = 'btnGirisYap'
KULLANICI_VARSAYILAN       = 'botan'
SIFRE_VARSAYILAN           = '152634'
KULLANICI_INDEX_VARSAYILAN = 3   # 4. item ('botan'). medula_settings.json
                                  # → 'medula_kullanici_index' ile override.

# Ana sayfada WinForms 'Giriş' butonu — IE login.jsp'de iken bu butona
# basılırsa MEDULA web oturumu açılır. UI Inspector kanıtı:
# Name='Giriş', auto_id='btnMedulayaGirisYap',
# ClassName='WindowsForms10.Window.b.app.0.134c08f_r8_ad1'
BUTTON_MEDULAYA_GIRIS      = 'btnMedulayaGirisYap'
LOGIN_JSP_URL_FRAGMENT     = 'login.jsp'   # IE doc URL'inde geçerse oturum yok

# Ana sayfada (Duyurular menüsü) bulunan kesin işaret — "Genel Duyurular"
# label'i. UI Inspector kanıtı: form1:tableExGenelDuyuruList:text2.
# Bu element varsa MEDULA web oturumu açık ve ana menüdeyiz.
ID_GENEL_DUYURULAR         = 'form1:tableExGenelDuyuruList:text2'

# Web (MSHTML id'leri — HTML kaynaklarından teyit edildi)
ID_MENU_RECETE_LISTESI     = 'form1:menuHtmlCommandExButton31'
ID_BUTTON_SORGULA_B_GRUBU  = 'form1:buttonSonlandirilmamisReceteler'
ID_TC_INPUT                = 'f:t18'
ID_BUTTON_RAPOR            = 'f:buttonRaporListesi'
ID_BUTTON_BITMIS_RAPORLAR  = 'form1:buttonBitmisRaporlariDaGoster'
ID_BUTTON_GERI_DON         = 'form1:buttonGeriDon'

# Reçete listesi satır pattern (rapor listesi kalıbından tahmin)
RECETE_LIST_PATTERN_TAHMINLER = (
    'form1:tableExReceteList:0:rowActionReceteSec',
    'form1:tableExReceteList:0:rowActionReceteIslem',
    'form1:tableExFaturaSonlandirilmamis:0:rowActionReceteSec',
    'form1:tableExSonlandirilmamisRecete:0:rowActionReceteSec',
)

# Rapor listesi satır pattern (HTML kaynağından teyit edildi)
RAPOR_LIST_TR_PREFIX        = 'TR_parentof_form1:tableExRaporTeshisList:'
RAPOR_LIST_ROWACTION_PREFIX = 'form1:tableExRaporTeshisList:'   # ::rowActionRaporSec
RAPOR_LIST_TEXT_PREFIX      = 'form1:tableExRaporTeshisList:'   # ::text14/15/96/97/98

# Adım 10 fallback için başlık elementi
RECETE_TABLO_BASLIK_TEXT = 'Sıra'
# Tablo başlığı altında 1. satıra inmek için piksel offset.
# UI Inspector ile 'Reçete No' başlığı yakalandı (boyut 65x30, Y=359);
# ilk satır TR yaklaşık 50dp altta — kullanıcı isteği 2026-05-25.
SATIR_YUKSEKLIK_DP       = 50
# Başlık aday listesi — sırasıyla denenir; 'Reçete No' kullanıcı tarafından
# UI Inspector ile doğrulandı (ControlType.Header), 'Sıra' eski anchor.
RECETE_TABLO_BASLIK_ADAYLAR = ('Reçete No', 'Sıra')

# Login takılma / donma tespiti
LOGIN_DONMA_ESIK_SN      = 30   # bu süre login başarısızsa donma kabul edilir
PROCESS_ADI              = 'BotanikMedula.exe'


class MedulaDurum(enum.Enum):
    """MEDULA'nın anlık durumu — `_medula_durum_tespit()` döner.

    State-aware navigatör, hangi adımdan başlayacağına göre karar verir:
      - KAPALI → exe başlat + login + ana sayfa
      - LOGIN_EKRANI → sadece login yap
      - LOGIN_DUSTU → taskkill + yeniden başlat
      - ANA_SAYFA → Reçete Listesi adımından başla
      - RECETE_LISTESI → ilk reçete satırını aç
      - RECETE_DETAY → TC alanı (f:t18) görünür, TC yaz + Rapor
      - RAPOR_LISTESI → satırları oku
      - BILINMEYEN → fallback: dikkatli devam et
    """
    KAPALI                = 'kapali'
    LOGIN_EKRANI          = 'login_ekrani'           # SifreSorForm açık
    LOGIN_DUSTU           = 'login_dustu'
    ANA_SAYFA_LOGIN_GEREK = 'ana_sayfa_login_gerek'  # IE login.jsp'de
    ANA_SAYFA             = 'ana_sayfa'              # MEDULA menüsü açık
    RECETE_LISTESI        = 'recete_listesi'
    RECETE_DETAY          = 'recete_detay'
    RAPOR_LISTESI         = 'rapor_listesi'
    BILINMEYEN            = 'bilinmeyen'


# ═════════════════════════════════════════════════════════════════════════
# 2. STATUS CALLBACK (kullanıcı GUI'den izleyebilsin)
# ═════════════════════════════════════════════════════════════════════════

StatusCb = Optional[Callable[[str], None]]


def _bildir(msg: str, cb: StatusCb = None) -> None:
    """Hem logger.info hem callback'e bildir."""
    logger.info(msg)
    if cb:
        try:
            cb(msg)
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════
# 3. PYWINAUTO + COM YARDIMCILARI
# ═════════════════════════════════════════════════════════════════════════

def _pywinauto_yukle():
    """pywinauto + send_keys lazy import — modül ithali zamanında dropdown
    olmasın diye lazy."""
    try:
        from pywinauto import Application, Desktop
        from pywinauto.keyboard import send_keys
        return Application, Desktop, send_keys
    except ImportError as e:
        raise RuntimeError(f'pywinauto bulunamadı: {e}') from e


def _medula_hwnd_bul() -> Optional[int]:
    """MEDULA ana penceresinin HWND'sini bul.

    strict=True ile çağrılır → BotanikEOS fallback'i devre dışı; sadece
    title'da "MEDULA" geçen WinForms pencere kabul edilir. Aksi takdirde
    login penceresi (BotanikEOS başlıklı) yanlışlıkla ana sayfa sanılıp
    state misdetect edilebilir.
    """
    try:
        from pencere_yerlesim import _medula_hwnd_bul as _bul
        return _bul(strict=True)
    except Exception:
        pass
    # Fallback: win32gui ile pencere tara
    try:
        import win32gui
        bulunan = [None]

        def _enum(h, _):
            try:
                t = win32gui.GetWindowText(h) or ''
                if ANASAYFA_TITLE in t and win32gui.IsWindowVisible(h):
                    bulunan[0] = h
                    return False
            except Exception:
                pass
            return True

        win32gui.EnumWindows(_enum, None)
        return bulunan[0]
    except Exception:
        return None


def _pencereyi_one_getir(hwnd: Optional[int],
                            cb: StatusCb = None) -> bool:
    """Pencereyi foreground'a al (SetForegroundWindow + ShowWindow restore).

    IE MSHTML COM erişimi pencere arka planda iken protected mode altında
    'Erişim engellendi' (HRESULT 0x80070005 = -2147024891) hatası verir.
    Sorgula/tıklama öncesinde garanti olarak çağrılır.

    Windows özelinde SetForegroundWindow başka bir process'ten çağrıldığında
    çoğu zaman engelleniyor; AttachThreadInput trick'i ile bypass edilir.
    """
    if not hwnd:
        return False
    try:
        import win32gui
        import win32con
        import win32process
        # Minimize ise restore et
        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement and placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass
        # AttachThreadInput trick — başka process'in input queue'sine bağlan
        try:
            fore_hwnd = win32gui.GetForegroundWindow()
            fore_thread = win32process.GetWindowThreadProcessId(fore_hwnd)[0]
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            cur_thread = win32process.GetCurrentThreadId() \
                if hasattr(win32process, 'GetCurrentThreadId') else None
        except Exception:
            fore_thread = target_thread = cur_thread = None
        try:
            import ctypes
            user32 = ctypes.windll.user32
            if cur_thread is None:
                cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            if fore_thread and fore_thread != cur_thread:
                user32.AttachThreadInput(cur_thread, fore_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            if fore_thread and fore_thread != cur_thread:
                user32.AttachThreadInput(cur_thread, fore_thread, False)
        except Exception as e:
            logger.debug('AttachThreadInput trick hatası: %s', e)
            # Fallback: doğrudan SetForegroundWindow (genelde başarısız)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
        return True
    except Exception as e:
        if cb:
            try:
                cb(f'[durum] pencere öne getirme hatası: {e}')
            except Exception:
                pass
        return False


def _medula_exe_path_cozumle() -> str:
    r"""Önce medula_settings.json'dan kayıtlı yolu oku; yoksa hardcoded.

    botanik_bot.py:7344 ile aynı yöntem — kullanıcı kurulum sihirbazında
    farklı bir yol kaydetmişse (C:\BotanikEczane yerine D:\... gibi) ona
    saygı gösteririz.
    """
    try:
        from medula_settings import get_medula_settings
        ms = get_medula_settings()
        yol = ms.get('medula_exe_path', '') or ''
        if yol and Path(yol).exists():
            return yol
    except Exception as e:
        logger.debug(f'medula_settings okunamadı: {e}')
    return MEDULA_EXE_PATH


def _kullanici_index_cozumle() -> int:
    """medula_settings.json'dan 'medula_kullanici_index' oku; yoksa 3.

    'botan' kullanıcısı login combobox'ında 4. item (0-based index=3).
    İleride farklı eczaneler için ayarlardan değiştirilebilir.
    """
    try:
        from medula_settings import get_medula_settings
        ms = get_medula_settings()
        val = ms.get('medula_kullanici_index', None)
        if val is not None and isinstance(val, int) and val >= 0:
            return val
    except Exception as e:
        logger.debug(f'medula_kullanici_index okunamadı: {e}')
    return KULLANICI_INDEX_VARSAYILAN


def _html_doc(medula_hwnd: Optional[int] = None):
    """MEDULA IE_Server'ında IHTMLDocument2 proxy döndür."""
    try:
        from medula_html_dom import html_doc_bul
        return html_doc_bul(medula_hwnd)
    except Exception as e:
        logger.warning(f'html_doc_bul hatası: {e}')
        return None


def _html_dom_hazir_bekle(medula_hwnd: Optional[int] = None,
                              sure_sn: float = 30.0,
                              cb: StatusCb = None,
                              js_init_bekle: float = 2.5):
    """MEDULA IE_Server'ı DOM proxy verene kadar bekle (max sure_sn).

    Login bittikten sonra MEDULA ana sayfa hwnd'i hemen görünüyor ama
    gömülü IE'nin Internet Explorer_Server child'ı + IHTMLDocument2
    proxy'si birkaç saniye sonra hazır oluyor. Bu fonksiyon sayfa
    gerçekten interaktif olana kadar bekler. None döner = timeout.

    js_init_bekle: readyState=complete olduktan sonra JS init için ek
    bekleme (saniye). Çok hızlı tıklama E_ACCESSDENIED veriyor.
    """
    deadline = time.time() + sure_sn
    deneme = 0
    while time.time() < deadline:
        deneme += 1
        doc = _html_doc(medula_hwnd)
        if doc is not None:
            try:
                rs = str(getattr(doc, 'readyState', 'complete')
                              or 'complete').lower()
                if rs == 'complete':
                    if deneme > 1:
                        _bildir(f'  ✓ DOM hazır ({deneme} deneme sonra)', cb)
                    # readyState=complete olsa bile MEDULA'nın JSF/Ajax
                    # script'leri biraz daha init zamanı istiyor — yoksa
                    # ilk .click() E_ACCESSDENIED veriyor.
                    if js_init_bekle > 0:
                        _bekle(js_init_bekle)
                        # Yeni proxy çek (eski stale olabilir)
                        d2 = _html_doc(medula_hwnd)
                        return d2 if d2 is not None else doc
                    return doc
            except Exception:
                return doc
        _bekle(0.4)
    _bildir(f'  ✗ DOM {sure_sn}s\'de hazır olmadı', cb)
    return None


def _ie_oturum_acik_mi(doc) -> bool:
    """MEDULA web oturumu açık mı? — Ana menü "Genel Duyurular" label'i
    (form1:tableExGenelDuyuruList:text2) varsa kesin oturum açıktır.

    Kullanıcı kanıtı (2026-05-21 UI Inspector): bu element ana sayfada
    görünür, login.jsp'de görünmez. URL-tabanlı kontrolden çok daha
    güvenilir çünkü MEDULA'nın URL'i bazen 'login.jsp' fragmentini
    barındırsa bile içerik ana menü olabiliyor.
    """
    if doc is None:
        return False
    try:
        elem = doc.getElementById(ID_GENEL_DUYURULAR)
        return elem is not None
    except Exception:
        return False


def _ie_login_jsp_mi(doc) -> bool:
    """MEDULA web oturumu KAPALI mı? — Genel Duyurular yok demek oturum
    açılmamış demek. Ek olarak URL'de login.jsp varsa kesinleşir.

    Mantık: ana menü Genel Duyurular VAR → oturum AÇIK → False
            Genel Duyurular YOK → oturum YOK → True (Giriş butonu lazım)
    """
    if doc is None:
        return False
    # Genel Duyurular varsa kesinlikle oturum açık
    if _ie_oturum_acik_mi(doc):
        return False
    # Genel Duyurular yok — büyük ihtimalle login.jsp veya transition
    try:
        url = ''
        try:
            url = str(doc.url or '')
        except Exception:
            pass
        if not url:
            try:
                url = str(doc.URL or '')
            except Exception:
                pass
        if LOGIN_JSP_URL_FRAGMENT in url.lower():
            return True
    except Exception:
        pass
    # URL belirsiz + Genel Duyurular yok → büyük ihtimalle login gerek
    return True


def _medulaya_3_kez_giris_dene(medula_hwnd: int,
                                    cb: StatusCb = None) -> bool:
    """Giriş butonuna 3 kez en az 1.5 sn aralıklarla bas; her basıştan
    sonra MEDULA web oturumu açılmış mı (Genel Duyurular göründü mü)
    kontrol et.

    Kullanıcı isteği (2026-05-21): basışlar arasında en az 1 sn olmalı —
    sayfa yüklenmeden tekrar basmamalı. 1.5 sn güvenli margin.
    3 deneme sonunda hala kapalıysa False — caller taskkill yapar.
    """
    BASIS_ARASI_SN = 1.5
    for deneme in range(1, 4):
        _bildir(f'Giriş butonu denemesi {deneme}/3...', cb)
        if not _medulaya_giris_butonuna_bas(medula_hwnd, cb=cb):
            _bekle(BASIS_ARASI_SN)
            continue
        # Buton basıldı; sayfa yüklensin diye bekle, sonra durumu kontrol et
        _bekle(BASIS_ARASI_SN)
        doc = _html_doc(medula_hwnd)
        if _ie_oturum_acik_mi(doc):
            _bildir(f'  ✓ Deneme {deneme} sonrası oturum açıldı '
                    '(Genel Duyurular görünür)', cb)
            return True
    _bildir('  ✗ 3 deneme sonrası hala oturum yok (Genel Duyurular bulunamadı)',
            cb)
    return False


def _medulaya_giris_butonuna_bas(medula_hwnd: int,
                                     cb: StatusCb = None) -> bool:
    """Ana sayfa WinForms 'Giriş' butonuna (btnMedulayaGirisYap) bas.

    IE_Server login.jsp gösteriyorsa ya da oturum düştüyse bu butona
    basıldığında MEDULA web oturumu yeniden başlatılır.

    UI Inspector raporu (2026-05-21):
      Name='Giriş', auto_id='btnMedulayaGirisYap',
      ClassName='WindowsForms10.Window.b.app.0.134c08f_r8_ad1'
    """
    Application, Desktop, send_keys = _pywinauto_yukle()
    try:
        _bildir('Ana sayfa Giriş butonu (btnMedulayaGirisYap) tıklanıyor', cb)
        app = Application(backend='uia').connect(handle=medula_hwnd, timeout=5)
        win = app.window(handle=medula_hwnd)
        btn = win.child_window(auto_id=BUTTON_MEDULAYA_GIRIS,
                                  control_type='Button')
        if not btn.exists(timeout=3):
            # Fallback: title ile ara
            btn = win.child_window(title='Giriş', control_type='Button')
            if not btn.exists(timeout=3):
                _bildir('  ✗ Giriş butonu bulunamadı', cb)
                return False
        try:
            btn.invoke()
        except Exception:
            btn.click_input()
        _bildir('  ✓ Giriş butonuna basıldı', cb)
        return True
    except Exception as e:
        _bildir(f'  ✗ Giriş butonu tıklama hatası: {e}', cb)
        return False


def _elem_tikla(doc, elem, elem_id: str, cb: StatusCb = None) -> bool:
    """IE COM elementine tıkla — 3 katmanlı fallback.

    1. elem.click() — direkt COM çağrısı
    2. elem.fireEvent('onclick') — onClick handler'ı tetikle
    3. doc.parentWindow.execScript("...click()", "JavaScript") — JS ile click

    MEDULA'nın JSF tabanlı sayfalarında ilk click() bazen E_ACCESSDENIED
    (0x80070005) veriyor — sayfa transition'da. fireEvent/execScript daha
    sabırlı.
    """
    # 1. Direkt click
    try:
        elem.click()
        return True
    except Exception as e1:
        _bildir(f'  click() başarısız, fireEvent denenecek: {e1}', cb)

    # 2. fireEvent onclick
    try:
        elem.fireEvent('onclick')
        _bildir('  ✓ fireEvent(onclick) ile tıklandı', cb)
        return True
    except Exception as e2:
        _bildir(f'  fireEvent başarısız, execScript denenecek: {e2}', cb)

    # 3. JS ile click — JSF id'sinde iki nokta var, CSS escape gerekli
    try:
        # getElementById koru — querySelector'da iki nokta escape gerekli
        js = (f'document.getElementById("{elem_id}").click();')
        try:
            doc.parentWindow.execScript(js, 'JavaScript')
        except Exception:
            # IHTMLDocument2 üzerinden execScript
            doc.execScript(js, 'JavaScript')
        _bildir('  ✓ execScript ile tıklandı', cb)
        return True
    except Exception as e3:
        _bildir(f'  ✗ Tüm tıklama yöntemleri başarısız: {e3}', cb)
        return False


def _bekle(saniye: float = 0.5) -> None:
    time.sleep(saniye)


# ═════════════════════════════════════════════════════════════════════════
# 3b. PROCESS / LOGIN PENCERESİ YARDIMCILARI
# ═════════════════════════════════════════════════════════════════════════

def _login_window_bul(cb: StatusCb = None):
    """SifreSorForm login penceresini bul — pywinauto Desktop tarama.

    recete_tarama.py:764-781'in kanıtlı yöntemi:
      Desktop(backend='uia').windows() → her pencerenin
      element_info.automation_id == 'SifreSorForm' kontrolü.

    BotanikEczane.exe (ana eczane uygulaması) da "BotanikEOS" başlıklı
    olduğu için title-based eşleştirme yanlış pencereyi yakalar.
    automation_id ile sadece BotanikMedula login penceresi seçilir.

    Returns: WindowSpecification (login_win) veya None.
    """
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend='uia')
        for w in desktop.windows():
            try:
                if w.element_info.automation_id == LOGIN_AUTOMATION_ID:
                    hwnd = w.handle
                    try:
                        return desktop.window(handle=hwnd)
                    except Exception:
                        return w
            except Exception:
                continue
    except Exception as e:
        _bildir(f'_login_window_bul hatası: {e}', cb)
    return None


def _login_hwnd_bul() -> Optional[int]:
    """SifreSorForm login penceresinin HWND'sini bul.

    SADECE automation_id='SifreSorForm' eşleşmesi. Title fallback YOK —
    çünkü BotanikEczane.exe (ana eczane uygulaması) da "BotanikEOS"
    başlıklı; title-match fallback'i o pencereyi yanlışlıkla yakalıyor
    ve state'i LOGIN_EKRANI sanıyor (login zaten başarılı olsa bile).
    """
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend='uia')
        for w in desktop.windows():
            try:
                if w.element_info.automation_id == LOGIN_AUTOMATION_ID:
                    return w.handle
            except Exception:
                continue
    except Exception:
        pass
    return None


def _medula_process_var_mi() -> bool:
    """BotanikMedula.exe process'i çalışıyor mu?"""
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            try:
                if (p.info.get('name') or '').lower() == PROCESS_ADI.lower():
                    return True
            except Exception:
                continue
    except ImportError:
        # psutil yoksa tasklist fallback
        try:
            out = subprocess.check_output(
                ['tasklist', '/FI', f'IMAGENAME eq {PROCESS_ADI}',
                 '/NH', '/FO', 'CSV'],
                stderr=subprocess.DEVNULL, timeout=5)
            return PROCESS_ADI.lower() in out.decode('utf-8', 'ignore').lower()
        except Exception:
            return False
    return False


def _medula_taskkill(cb: StatusCb = None) -> bool:
    """BotanikMedula.exe process'ini zorla kapat (login takılırsa)."""
    try:
        _bildir(f'taskkill /F /IM {PROCESS_ADI} çalıştırılıyor...', cb)
        subprocess.run(['taskkill', '/F', '/IM', PROCESS_ADI],
                       check=False, capture_output=True, timeout=10)
        _bekle(1.5)   # process tamamen kapansın
        # Hala var mı kontrol et
        if _medula_process_var_mi():
            _bildir('UYARI: taskkill sonrası process hala var', cb)
            return False
        _bildir('✓ Medula process kapatıldı', cb)
        return True
    except Exception as e:
        _bildir(f'taskkill hatası: {e}', cb)
        return False


def _medula_durum_tespit(cb: StatusCb = None) -> MedulaDurum:
    """MEDULA'nın hangi durumda olduğunu tespit et (state machine).

    Sırayla kontrol eder:
      1. Process yok → KAPALI
      2. Login penceresi açık → LOGIN_EKRANI
      3. Ana sayfa HWND yok ama process var → LOGIN_DUSTU
      4. Ana sayfa açık → içeride hangi sayfa?
         - TC input (f:t18) varsa → RECETE_DETAY
         - Rapor listesi (rapor_takip_no başlığı) → RAPOR_LISTESI
         - Reçete listesi (rowClass1/2) → RECETE_LISTESI
         - Hiçbiri → ANA_SAYFA
    """
    # 1. Process var mı?
    if not _medula_process_var_mi():
        _bildir('[durum] Process yok → KAPALI', cb)
        return MedulaDurum.KAPALI

    # 2. Login penceresi açık mı?
    if _login_hwnd_bul():
        _bildir('[durum] Login penceresi açık → LOGIN_EKRANI', cb)
        return MedulaDurum.LOGIN_EKRANI

    # 3. Ana sayfa HWND var mı?
    main_hwnd = _medula_hwnd_bul()
    if not main_hwnd:
        _bildir('[durum] Process var ama ana sayfa yok → LOGIN_DUSTU', cb)
        return MedulaDurum.LOGIN_DUSTU

    # Bulunan ana sayfa hwnd'in title'ını logla (yanlış pencere debug için)
    try:
        import win32gui
        bulunan_title = win32gui.GetWindowText(main_hwnd) or ''
        _bildir(f'[durum] Ana sayfa hwnd={main_hwnd}, title="{bulunan_title}"',
                cb)
    except Exception:
        pass

    # 4. Ana sayfa açık — içeride hangi sayfa?
    doc = _html_doc(main_hwnd)
    if doc is None:
        _bildir('[durum] HTML DOM okunamıyor → ANA_SAYFA (fallback)', cb)
        return MedulaDurum.ANA_SAYFA

    # 4.0a Genel Duyurular varsa kesin ana menüdeyiz (oturum açık).
    # Bu kontrol f:t18 false positive'ini aşar — menü sayfasında bile
    # gizli f:t18 olabiliyor, ama Genel Duyurular sadece menüde var.
    if _ie_oturum_acik_mi(doc):
        _bildir('[durum] Genel Duyurular görünür → ANA_SAYFA (menüde)', cb)
        return MedulaDurum.ANA_SAYFA

    # 4.0b Genel Duyurular yok + login.jsp → oturum gerekli
    if _ie_login_jsp_mi(doc):
        _bildir('[durum] Genel Duyurular yok → ANA_SAYFA_LOGIN_GEREK', cb)
        return MedulaDurum.ANA_SAYFA_LOGIN_GEREK

    # 4a. Reçete detayında TC alanı var mı?
    # getElementById('f:t18') menü sayfasında bile non-None dönebilir
    # (gizli template elementi). offsetParent ile gerçekten görünür mü
    # kontrol et — sadece render tree'de olan elementler RECETE_DETAY sayar.
    try:
        elem_tc = doc.getElementById(ID_TC_INPUT)
        if elem_tc is not None:
            try:
                op = elem_tc.offsetParent
                if op is not None:
                    _bildir('[durum] TC alanı (f:t18) görünür → RECETE_DETAY',
                            cb)
                    return MedulaDurum.RECETE_DETAY
            except Exception:
                # offsetParent okunamadıysa, ek kontrol: rapor butonu da var mı
                try:
                    if doc.getElementById(ID_BUTTON_RAPOR) is not None:
                        _bildir('[durum] TC + Rapor butonu var → RECETE_DETAY',
                                cb)
                        return MedulaDurum.RECETE_DETAY
                except Exception:
                    pass
    except Exception:
        pass

    # 4b. Rapor listesi açık mı? (text14 = ilk rapor takip no, görünür mü)
    try:
        rapor_elem = doc.getElementById(f'{RAPOR_LIST_TEXT_PREFIX}0:text14')
        if rapor_elem is not None:
            try:
                if rapor_elem.offsetParent is not None:
                    _bildir('[durum] Rapor takip no görünür → RAPOR_LISTESI',
                            cb)
                    return MedulaDurum.RAPOR_LISTESI
            except Exception:
                _bildir('[durum] Rapor takip no var → RAPOR_LISTESI', cb)
                return MedulaDurum.RAPOR_LISTESI
    except Exception:
        pass

    # 4c. Reçete listesi açık mı? (rowClass1/2 satırları)
    try:
        for cls in ('rowClass1', 'rowClass2'):
            rs = doc.getElementsByClassName(cls)
            if rs and rs.length > 0:
                _bildir(f'[durum] Reçete satırları görünür ({cls}) '
                        '→ RECETE_LISTESI', cb)
                return MedulaDurum.RECETE_LISTESI
    except Exception:
        pass

    # 4d. Reçete Listesi menü butonu görünür mü? (ana sayfa)
    try:
        if doc.getElementById(ID_MENU_RECETE_LISTESI) is not None:
            _bildir('[durum] Reçete Listesi menüsü → ANA_SAYFA', cb)
            return MedulaDurum.ANA_SAYFA
    except Exception:
        pass

    _bildir('[durum] BILINMEYEN — fallback', cb)
    return MedulaDurum.BILINMEYEN


# ═════════════════════════════════════════════════════════════════════════
# 4. ADIM 1-7 — Medula başlat + login + ana sayfa
# ═════════════════════════════════════════════════════════════════════════

def _combo_kullanici_sec_index(combo, kullanici_index: int, send_keys,
                                  cb: StatusCb = None) -> bool:
    """ComboBox'tan INDEX ile kullanıcı seç — botanik_bot.py:7484-7495 kanıtlı.

    Name-based arama ('botan' yazıp typeahead) WinForms DropDownList'te
    güvenilir değil (kullanıcı item_texts() boş döndürüyor / typewrite
    karakter düşürüyor). İndex tabanlı seçim KANITLI çalışıyor.

    Akış: click_input + Alt+Down (dropdown aç) + Home (en başa) + Down × N
    + Enter. Home tuşu ilk item garantili highlight olsun diye.

    kullanici_index = 3 → 4. item ('botan' default).
    """
    try:
        import pyautogui
    except ImportError:
        pyautogui = None

    # Strateji 1: pyautogui (botanik_bot.py:7484-7495 kanıtlı yöntem)
    if pyautogui is not None:
        try:
            combo.click_input()
            _bekle(0.3)
            # Alt+Down → dropdown aç
            pyautogui.keyDown('alt')
            pyautogui.press('down')
            pyautogui.keyUp('alt')
            _bekle(0.6)
            # Home → en başa dön (önceki seçim varsa sıfırlansın)
            pyautogui.press('home')
            _bekle(0.2)
            # Down × N → N. itemse (0-based, Home zaten 1. itemde)
            for i in range(kullanici_index):
                pyautogui.press('down')
                _bekle(0.15)
            pyautogui.press('enter')
            _bekle(0.5)
            _bildir(f'  ✓ Kullanıcı index={kullanici_index} seçildi '
                    f'(Alt↓+Home+↓×{kullanici_index}+Enter)', cb)
            return True
        except Exception as e:
            logger.debug(f'pyautogui index seçim hatası: {e}')
            _bildir(f'  pyautogui yöntemi başarısız: {e}', cb)

    # Strateji 2: pywinauto send_keys fallback
    try:
        combo.click_input()
        _bekle(0.3)
        send_keys('%{DOWN}', pause=0.1)   # Alt+Down
        _bekle(0.6)
        send_keys('{HOME}', pause=0.1)
        _bekle(0.2)
        for i in range(kullanici_index):
            send_keys('{DOWN}', pause=0.15)
        send_keys('{ENTER}', pause=0.1)
        _bekle(0.4)
        _bildir(f'  ✓ Kullanıcı index={kullanici_index} seçildi (send_keys)',
                cb)
        return True
    except Exception as e:
        _bildir(f'  ✗ Index seçim tamamen başarısız: {e}', cb)
        return False


def medula_baslat_ve_giris(kullanici: str = KULLANICI_VARSAYILAN,
                              sifre: str = SIFRE_VARSAYILAN,
                              exe_path: Optional[str] = None,
                              cb: StatusCb = None,
                              taskkill_recovery: bool = True) -> bool:
    """Adım 1-7: Botanik Medula'yı çalıştır + login + ana sayfa hazır.

    State-aware — mevcut duruma göre uygun adımdan başlar:
      - ANA_SAYFA / RECETE_*  → True döner (login gereksiz)
      - LOGIN_EKRANI → mevcut login penceresinde sadece giriş yap
      - LOGIN_DUSTU → taskkill ile öldür, yeniden başlat (taskkill_recovery=True)
      - KAPALI → exe başlat + login

    Returns: True = ana sayfa hazır, False = hata.
    """
    Application, Desktop, send_keys = _pywinauto_yukle()

    # Exe path: settings'ten oku, yoksa default
    if exe_path is None:
        exe_path = _medula_exe_path_cozumle()

    # State tespit
    durum = _medula_durum_tespit(cb=cb)
    if durum in (MedulaDurum.ANA_SAYFA, MedulaDurum.RECETE_LISTESI,
                 MedulaDurum.RECETE_DETAY, MedulaDurum.RAPOR_LISTESI,
                 MedulaDurum.ANA_SAYFA_LOGIN_GEREK):
        _bildir(f'✓ Medula zaten açık ({durum.value}) — '
                f'SifreSorForm girişi atlanıyor', cb)
        return True

    # LOGIN_DUSTU → taskkill + yeniden başlat
    if durum == MedulaDurum.LOGIN_DUSTU and taskkill_recovery:
        _bildir('Medula process var ama pencere düşmüş — taskkill+yeniden', cb)
        _medula_taskkill(cb=cb)
        durum = MedulaDurum.KAPALI

    # KAPALI → exe başlat
    if durum == MedulaDurum.KAPALI:
        _bildir(f'BotanikMedula başlatılıyor: {exe_path}', cb)
        if not Path(exe_path).exists():
            _bildir(f'❌ HATA: BotanikMedula.exe bulunamadı: {exe_path}\n'
                    f'   Kurulum sihirbazından doğru yolu ayarlayın '
                    f'(medula_settings.json → medula_exe_path).', cb)
            return False
        try:
            subprocess.Popen([exe_path], cwd=str(Path(exe_path).parent),
                             shell=False)
        except Exception as e:
            _bildir(f'❌ HATA: exe başlatılamadı: {e}', cb)
            return False

        # Login penceresi gelene kadar bekle (max 15 sn)
        _bildir('Login penceresi bekleniyor...', cb)
        for _ in range(30):
            _bekle(0.5)
            if _login_hwnd_bul():
                break
        else:
            _bildir('HATA: Login penceresi açılmadı (15 sn timeout)', cb)
            return False
        # Pencere göründü ama içerideki WinForms kontrolleri tam yerleşmemiş
        # olabilir — combobox/edit'ler render olana kadar 2 sn bekle (cold
        # start'ta lisans/network kontrolü yapılıyor olabilir)
        _bekle(2.0)

    # Şimdi login penceresinde olmalıyız (LOGIN_EKRANI ya da yeni başlatıldı)
    if not _login_hwnd_bul():
        _bildir('HATA: Login penceresi bulunamadı', cb)
        return False

    # Login penceresini SifreSorForm automation_id ile bul (kanıtlı yöntem
    # recete_tarama.py:764). title_re kullanmayız çünkü BotanikEczane.exe
    # (ana eczane uygulaması) de "BotanikEOS" başlıklı olabilir.
    login_win = None
    for _ in range(10):
        login_win = _login_window_bul(cb=cb)
        if login_win is not None:
            break
        _bekle(0.5)
    if login_win is None:
        _bildir('HATA: SifreSorForm login penceresine bağlanılamadı '
                '(pencere açık ama UIA yanıt vermiyor)', cb)
        # Donmuş login → taskkill + yeniden başlat (tek seferlik recovery)
        if taskkill_recovery:
            _bildir('Login penceresi donuk — taskkill ile temiz başlatılıyor',
                    cb)
            _medula_taskkill(cb=cb)
            return medula_baslat_ve_giris(
                kullanici=kullanici, sifre=sifre, exe_path=exe_path,
                cb=cb, taskkill_recovery=False)
        return False

    try:
        _bildir(f'✓ SifreSorForm bağlandı (hwnd={getattr(login_win, "handle", "?")})',
                cb)
        # Pencereyi öne getir — focus garanti
        try:
            login_win.set_focus()
            _bekle(0.3)
        except Exception:
            pass

        # Adım 3-4: cmbKullanicilar → index ile kullanıcı seç
        kullanici_index = _kullanici_index_cozumle()
        _bildir(f'Kullanıcı seçiliyor: index={kullanici_index} '
                f'(varsayılan 3 = 4. item "botan")', cb)
        combo = login_win.child_window(auto_id=COMBO_KULLANICI,
                                          control_type='ComboBox')
        # 15 sn timeout — cold start'ta BotanikMedula combobox'ı geç render
        # ediyor (lisans/ağ kontrolü). exists önce, sonra visible bekle.
        try:
            combo.wait('exists', timeout=15)
            combo.wait('visible', timeout=15)
        except Exception as e:
            _bildir(f'HATA: Kullanıcı combobox\'ı 15 sn içinde gelmedi: {e}', cb)
            raise
        if not _combo_kullanici_sec_index(combo, kullanici_index, send_keys,
                                              cb=cb):
            _bildir('HATA: Kullanıcı index seçimi başarısız', cb)
            return False

        # Adım 5: txtSifre → şifre (set_text + send_keys fallback)
        _bildir('Şifre giriliyor', cb)
        sifre_edit = login_win.child_window(auto_id=EDIT_SIFRE,
                                              control_type='Edit')
        sifre_edit.wait('visible', timeout=15)
        # Önce set_text dene (en güvenilir)
        sifre_yazildi = False
        try:
            sifre_edit.set_text(sifre)
            _bekle(0.2)
            sifre_yazildi = True
            _bildir('  ✓ Şifre set_text ile yazıldı', cb)
        except Exception as e:
            logger.debug(f'set_text hatası: {e}')
        if not sifre_yazildi:
            try:
                sifre_edit.click_input()
                _bekle(0.15)
                send_keys('^a', pause=0.05)
                send_keys('{DEL}', pause=0.05)
                send_keys(sifre, pause=0.04)
                _bekle(0.2)
                _bildir('  ✓ Şifre send_keys ile yazıldı', cb)
            except Exception as e:
                _bildir(f'HATA: Şifre yazılamadı: {e}', cb)
                return False

        # Adım 6: Giriş butonu (invoke → click_input fallback)
        _bildir('Giriş butonu', cb)
        giris_btn = login_win.child_window(auto_id=BUTTON_GIRIS,
                                              control_type='Button')
        giris_btn.wait('enabled', timeout=15)
        try:
            giris_btn.invoke()
        except Exception:
            try:
                giris_btn.click_input()
            except Exception as e:
                _bildir(f'HATA: Giriş butonu tıklanamadı: {e}', cb)
                return False
    except Exception as e:
        _bildir(f'Login adımları hatası: {e}', cb)
        # LOGIN_DUSTU benzeri durum — recovery dene
        if taskkill_recovery:
            _bildir('Login takıldı — taskkill ile yeniden başlatılıyor', cb)
            _medula_taskkill(cb=cb)
            return medula_baslat_ve_giris(
                kullanici=kullanici, sifre=sifre, exe_path=exe_path,
                cb=cb, taskkill_recovery=False)  # tek seferlik recovery
        return False

    # Adım 7: Ana sayfa gelene kadar bekle (max 30 sn)
    _bildir('Ana sayfa bekleniyor...', cb)
    bekleme_basla = time.time()
    main_hwnd = None
    while time.time() - bekleme_basla < 30:
        _bekle(0.5)
        main_hwnd = _medula_hwnd_bul()
        if main_hwnd:
            _bildir('✓ MEDULA ana sayfa hazır (hwnd alındı)', cb)
            break
        # Login hala açık ama uzun sürüyor → donma olabilir
        if (time.time() - bekleme_basla > LOGIN_DONMA_ESIK_SN
                and _login_hwnd_bul()):
            break
    if main_hwnd:
        # Hwnd hazır ama gömülü IE DOM'u henüz oluşmamış olabilir —
        # interaktif olana kadar bekle. Yoksa ilk recete_listesi adımı
        # 'HTML DOM proxy alınamadı' hatasıyla bailout veriyor.
        _bildir('DOM hazır olana kadar bekleniyor (IE_Server)...', cb)
        if _html_dom_hazir_bekle(main_hwnd, sure_sn=30.0, cb=cb) is not None:
            _bildir('✓ MEDULA DOM interaktif', cb)
            return True
        # DOM gelmediyse de True dönüyoruz — belki sonraki adımda toparlar
        _bildir('UYARI: DOM hazır göstergesi alınamadı, devam ediliyor', cb)
        return True

    _bildir(f'HATA: Ana sayfa {LOGIN_DONMA_ESIK_SN} sn içinde açılmadı', cb)
    if taskkill_recovery and _login_hwnd_bul():
        _bildir('Login donmuş — taskkill ile yeniden başlatılıyor', cb)
        _medula_taskkill(cb=cb)
        return medula_baslat_ve_giris(
            kullanici=kullanici, sifre=sifre, exe_path=exe_path,
            cb=cb, taskkill_recovery=False)
    return False


# ═════════════════════════════════════════════════════════════════════════
# 5. ADIM 8-9 — Reçete Listesi + B grubu sorgula
# ═════════════════════════════════════════════════════════════════════════

def recete_listesi_b_grubu_ac(cb: StatusCb = None) -> bool:
    """Adım 8-9b: Sol menü Reçete Listesi → B grubu → Sorgula.

    Kullanıcı kararı (2026-05-25):
    1) Önce mevcut Medula penceresini ÖNE GETİR (COM 'Erişim engellendi'
       hatasını önler — IE protected mode pencere arka planda iken DOM
       erişimini engeller).
    2) Sorgula tıklama hatası alınırsa LOKAL olarak 3 kez Giriş butonu
       denenir + retry (oturum düşmüş olabilir; üst akış taskkill yapmadan
       önce bu lokal kurtarma denenir).
    """
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        _bildir('HATA: Medula penceresi bulunamadı', cb)
        return False

    # 1) Pencereyi öne getir — COM erişim engellendi hatasını önler
    _pencereyi_one_getir(medula_hwnd, cb=cb)
    _bekle(0.4)  # foreground geçişi tamamlansın

    # DOM proxy 15sn'ye kadar bekleme — IE_Server cold load için tolerans
    doc = _html_dom_hazir_bekle(medula_hwnd, sure_sn=15.0, cb=cb)
    if doc is None:
        _bildir('HATA: HTML DOM proxy 15sn içinde alınamadı', cb)
        return False

    # Adım 8: Sol menü Reçete Listesi
    try:
        _bildir('Sol menü → Reçete Listesi', cb)
        elem = doc.getElementById(ID_MENU_RECETE_LISTESI)
        if elem is None:
            _bildir(f'HATA: {ID_MENU_RECETE_LISTESI} bulunamadı', cb)
            return False
        if not _elem_tikla(doc, elem, ID_MENU_RECETE_LISTESI, cb=cb):
            return False
        # Sayfa yüklensin — bekleme + sonraki adımda DOM hazır bekleme yapılır
        _bekle(2.5)
    except Exception as e:
        _bildir(f'Reçete Listesi tıklama hatası: {e}', cb)
        return False

    # Sayfa değişti — yeni doc al (DOM hazır olmasını bekle)
    doc = _html_dom_hazir_bekle(medula_hwnd, sure_sn=15.0, cb=cb)
    if doc is None:
        _bildir('HATA: Reçete Listesi sayfası DOM yok', cb)
        return False

    # Adım 9: B grubu — TD[veri="4"]
    try:
        _bildir('B grubu seçiliyor', cb)
        try:
            b_td = doc.querySelector('td[veri="4"]')
        except Exception:
            # Fallback: tüm TD'leri gez
            b_td = None
            tds = doc.getElementsByTagName('TD')
            for i in range(tds.length):
                t = tds.item(i)
                try:
                    if t.getAttribute('veri') == '4' and (t.innerText or '').strip() == 'B':
                        b_td = t
                        break
                except Exception:
                    continue
        if b_td is None:
            _bildir('HATA: B grubu TD bulunamadı', cb)
            return False
        if not _elem_tikla(doc, b_td, 'td[veri="4"]', cb=cb):
            return False
        # B grubu seçimi sayfa transition'ı tetikleyebilir — bekle
        _bekle(1.5)
    except Exception as e:
        _bildir(f'B grubu tıklama hatası: {e}', cb)
        return False

    # Adım 9b: Sorgula — başarısız ise lokal 3-deneme-giriş + retry
    # B grubu tıklaması sayfa transition'ı tetikler; MSHTML COM proxy
    # henüz oturmadan getElementById/click yapılırsa E_ACCESSDENIED
    # (0x80070005) fırlar. Sorgula çağrısının HER seferinde önce pencereyi
    # öne getir + DOM tazele + 2 iç-deneme yap.
    def _sorgula_dene(doc_local) -> Tuple[bool, str]:
        _pencereyi_one_getir(medula_hwnd, cb=cb)
        _bekle(0.4)
        doc_fresh = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
        if doc_fresh is not None:
            doc_local = doc_fresh
        son_hata = ''
        for ic_deneme in range(1, 3):
            try:
                _bildir(f'Sorgula (iç-deneme {ic_deneme}/2)', cb)
                sorgula_btn = doc_local.getElementById(
                    ID_BUTTON_SORGULA_B_GRUBU)
                if sorgula_btn is None:
                    return (False,
                            f'{ID_BUTTON_SORGULA_B_GRUBU} bulunamadı')
                if not _elem_tikla(doc_local, sorgula_btn,
                                     ID_BUTTON_SORGULA_B_GRUBU, cb=cb):
                    son_hata = 'elem_tikla False döndü'
                else:
                    _bekle(2.0)
                    return (True, '')
            except Exception as ee:
                son_hata = str(ee)
            if ic_deneme < 2:
                _bildir(f'  Sorgula iç-retry ({son_hata}) — pencere öne + '
                        'DOM tazele', cb)
                _pencereyi_one_getir(medula_hwnd, cb=cb)
                _bekle(0.6)
                fresh = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0,
                                                cb=cb)
                if fresh is not None:
                    doc_local = fresh
        return (False, son_hata)

    ok, hata = _sorgula_dene(doc)
    if ok:
        _bildir('✓ Reçete listesi (B grubu) açıldı', cb)
        return True

    _bildir(f'Sorgula tıklama hatası: {hata} — lokal kurtarma deneniyor',
            cb)
    # Lokal kurtarma: pencereyi öne getir + 3 kez Giriş butonu + retry
    _pencereyi_one_getir(medula_hwnd, cb=cb)
    _bekle(0.4)
    # Oturum düşmüş olabilir — Giriş butonu 3 deneme (mevcut helper)
    try:
        _medulaya_3_kez_giris_dene(medula_hwnd, cb=cb)
    except Exception as e:
        _bildir(f'[durum] lokal 3-deneme-giriş hatası: {e}', cb)

    # Sayfayı yeniden çağırıp Sorgula'yı bir kez daha dene
    doc2 = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
    if doc2 is None:
        _bildir('Lokal kurtarma: DOM proxy alınamadı', cb)
        return False
    # Sol menü Reçete Listesi'ne yeniden tıkla (sayfa farklı olabilir)
    try:
        elem2 = doc2.getElementById(ID_MENU_RECETE_LISTESI)
        if elem2 is not None:
            _elem_tikla(doc2, elem2, ID_MENU_RECETE_LISTESI, cb=cb)
            _bekle(1.5)
            doc2 = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
        # B grubu yeniden seç
        if doc2 is not None:
            try:
                b_td2 = doc2.querySelector('td[veri="4"]')
                if b_td2 is not None:
                    _elem_tikla(doc2, b_td2, 'td[veri="4"]', cb=cb)
                    _bekle(0.5)
            except Exception:
                pass
    except Exception as e:
        _bildir(f'Lokal kurtarma re-navigation hatası: {e}', cb)

    ok2, hata2 = _sorgula_dene(doc2) if doc2 else (False, 'doc2 None')
    if ok2:
        _bildir('✓ Lokal kurtarma başarılı — Reçete listesi (B grubu) açıldı',
                cb)
        return True
    _bildir(f'Lokal kurtarma da başarısız: {hata2}', cb)
    return False


# ═════════════════════════════════════════════════════════════════════════
# 6. ADIM 11 — Reçete listesi 1. satır seç (3 katmanlı fallback)
# ═════════════════════════════════════════════════════════════════════════

def ilk_recete_satirini_ac(cb: StatusCb = None) -> bool:
    """Adım 11: Reçete listesindeki 1. satıra tıkla → reçete detay sayfası.

    3 katmanlı fallback (2026-05-25 revize):
        1. dispatchEvent + MouseEvent click — IBM HxClient tableEx
           addEventListener handler'larını tetikler (gerçek mouse click
           simülasyonu). DOĞRULANDI: f:t18 detay sayfasına geçer.
        2. Pattern guess: bilinen form1:tableExReceteList:0:... id'leri
           üzerinde eski .click() — eski Medula sürümleri için fallback.
        3. Tablo başlığı (Reçete No / Sıra) altına 50dp element-relative
           click_input (gerçek mouse click — son çare).

    Her katmandan sonra reçete detay sayfasına geçildiği f:t18 polling
    ile doğrulanır; geçilmediyse sonraki katmana düşer.
    """
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        _bildir('HATA: Medula penceresi yok', cb)
        return False

    # Pencere öne — DOM erişim ve focus için garanti
    _pencereyi_one_getir(medula_hwnd, cb=cb)
    _bekle(0.4)

    doc = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
    if doc is None:
        doc = _html_doc(medula_hwnd)

    # ── Katman 1: dispatchEvent ile MouseEvent click (2026-05-25 doğrulandı) ──
    # IBM HxClient tableEx widget'ı TR'lere addEventListener ile click handler
    # ekler. IE COM `.click()` ve `.fireEvent('onclick')` bu listener'ları
    # tetiklemez. dispatchEvent + initMouseEvent ise gerçek MouseEvent oluştu-
    # rur ve addEventListener handler'ları tetikler → form submit + detay sayfa.
    if doc is not None:
        try:
            _bildir('Adım 11 — Katman 1: dispatchEvent (TR_parentof)', cb)
            _debug_html_dump(doc, 'recete_listesi.html', cb)
            tr_id = ('TR_parentof_form1:tableExReceteList:0:'
                     'rowActionReceteSec')
            js = (
                "(function(){"
                f"var tr=document.getElementById(\"{tr_id}\");"
                "if(!tr){return;}"
                "var ev;"
                "if(document.createEvent){"
                "ev=document.createEvent('MouseEvents');"
                "ev.initMouseEvent('click',true,true,window,1,0,0,0,0,"
                "false,false,false,false,0,null);"
                "tr.dispatchEvent(ev);"
                "}else if(document.createEventObject){"
                "ev=document.createEventObject();"
                "tr.fireEvent('onclick',ev);"
                "}"
                "})();"
            )
            try:
                doc.parentWindow.execScript(js, 'JavaScript')
            except Exception as e:
                _bildir(f'  Katman 1 execScript hatası: {e}', cb)
                raise
            # Sayfa yüklensin — DOM hazır bekleme + ek margin
            _bekle(3.0)
            _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
            # Detay sayfasına geçilmiş mi doğrula: f:t18 var mı?
            if _recete_detay_sayfasinda_mi(medula_hwnd, sure_sn=5.0):
                _bildir('✓ 1. satır tıklandı (dispatchEvent → detay sayfası)',
                        cb)
                return True
            _bildir('  Katman 1 sonrası detay sayfasına geçilmedi, Katman 2',
                    cb)
        except Exception as e:
            logger.debug(f'Katman 1 hatası: {e}')

    # ── Katman 2: Pattern guess (eski klik metodu — geriye dönük fallback) ──
    if doc is not None:
        try:
            _bildir('Adım 11 — Katman 2: pattern guess', cb)
            for pid in RECETE_LIST_PATTERN_TAHMINLER:
                try:
                    elem = doc.getElementById(pid)
                    if elem is not None:
                        elem.click()
                        _bekle(3.0)
                        _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0,
                                                cb=cb)
                        if _recete_detay_sayfasinda_mi(medula_hwnd,
                                                          sure_sn=5.0):
                            _bildir(
                                f'✓ 1. satır tıklandı (pattern: {pid})', cb)
                            return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f'Katman 2 hatası: {e}')

    # ── Katman 3: Başlık + 50dp altı element-relative ──
    return _ilk_satir_baslik_fallback(medula_hwnd, cb)


def _recete_detay_sayfasinda_mi(medula_hwnd: int, sure_sn: float = 5.0) -> bool:
    """Reçete detay sayfasına geçilip geçilmediğini f:t18 (TC alanı) ile
    doğrular. 0.5sn aralıklarla polling, max sure_sn."""
    import time as _t
    son = _t.time() + sure_sn
    while _t.time() < son:
        try:
            doc = _html_doc(medula_hwnd)
            if doc is not None and doc.getElementById(ID_TC_INPUT) is not None:
                return True
        except Exception:
            pass
        _bekle(0.5)
    return False


def _ilk_satir_baslik_fallback(medula_hwnd: int, cb: StatusCb = None) -> bool:
    """Katman 3: Tablo başlığı altına SATIR_YUKSEKLIK_DP tıkla
    (element-relative, mutlak ekran koord. değil).

    Başlık adayları sırayla denenir (Header → Text control_type). Kullanıcı
    isteği 2026-05-25: 50dp altındaki ilk satıra tıkla.
    """
    Application, Desktop, send_keys = _pywinauto_yukle()
    try:
        _bildir(f'Adım 11 — Katman 3: başlık+{SATIR_YUKSEKLIK_DP}dp fallback',
                cb)
        app = Application(backend='uia').connect(handle=medula_hwnd, timeout=3)
        win = app.window(handle=medula_hwnd)

        # Aday başlıkları sırayla dene; her aday için önce Header sonra Text
        h = None
        kullanilan = None
        for aday in RECETE_TABLO_BASLIK_ADAYLAR:
            for ct in ('Header', 'Text'):
                try:
                    bulunan = win.descendants(title=aday, control_type=ct)
                except Exception:
                    bulunan = []
                if bulunan:
                    h = bulunan[0]
                    kullanilan = f'{aday} ({ct})'
                    break
            if h is not None:
                break
        if h is None:
            adaylar_str = ', '.join(RECETE_TABLO_BASLIK_ADAYLAR)
            _bildir(f'HATA: başlık adayları bulunamadı ({adaylar_str})', cb)
            return False

        rect = h.rectangle()
        # Element-içi koord: (width/2, height + SATIR_YUKSEKLIK_DP)
        x_in = rect.width() // 2
        y_in = rect.height() + SATIR_YUKSEKLIK_DP
        try:
            h.click_input(coords=(x_in, y_in))
            # Sayfa yüklensin — DOM hazır bekleme + ek margin
            _bekle(3.0)
            _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
            if _recete_detay_sayfasinda_mi(medula_hwnd, sure_sn=5.0):
                _bildir(f'✓ "{kullanilan}" altı +{SATIR_YUKSEKLIK_DP}dp '
                        'tıklandı (detay sayfası)', cb)
                return True
            _bildir(f'UYARI: "{kullanilan}" altı tıklandı ama detay sayfasına '
                    'geçilemedi', cb)
            return False
        except Exception as e:
            _bildir(f'click_input hatası: {e}', cb)
            return False
    except Exception as e:
        _bildir(f'Fallback hatası: {e}', cb)
        return False


# ═════════════════════════════════════════════════════════════════════════
# 7. ADIM 12-15 — TC yapıştır + Rapor + Bitmiş Raporları da Göster
# ═════════════════════════════════════════════════════════════════════════

def tc_yaz_ve_raporlari_ac(tc: str, cb: StatusCb = None) -> bool:
    """Adım 12-15: f:t18'e TC yaz → f:buttonRaporListesi → BitmisRaporlari."""
    Application, Desktop, send_keys = _pywinauto_yukle()

    if not tc or not (len(tc) == 11 and tc.isdigit()):
        _bildir(f'HATA: Geçersiz TC: {tc!r}', cb)
        return False

    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        _bildir('HATA: Medula penceresi yok', cb)
        return False

    # Reçete detay sayfası yüklensin diye DOM proxy + f:t18 polling
    # (1. satır tıklamasından sonra sayfa transition'ı sürerken çağrılıyor)
    doc = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
    if doc is None:
        doc = _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: HTML DOM proxy yok', cb)
        return False

    # Adım 12-13: TC alanı temizle + yaz
    try:
        _bildir(f'Adım 12 — TC alanına {tc} yazılıyor', cb)
        # f:t18 polling — sayfa yüklenirken 15sn'ye kadar elementi bekle
        tc_input = None
        for _ in range(30):
            try:
                tc_input = doc.getElementById(ID_TC_INPUT)
            except Exception:
                tc_input = None
            if tc_input is not None:
                break
            _bekle(0.5)
            # DOM'u tazele — sayfa transition'da yeni doc gerekebilir
            try:
                yeni_doc = _html_doc(medula_hwnd)
                if yeni_doc is not None:
                    doc = yeni_doc
            except Exception:
                pass
        if tc_input is None:
            _bildir(f'HATA: {ID_TC_INPUT} bulunamadı (15sn polling)', cb)
            return False
        # DOM'da doğrudan value set + change event tetikle
        try:
            tc_input.value = tc
            tc_input.focus()
            try:
                tc_input.fireEvent('onchange')
            except Exception:
                pass
            _bekle(0.3)
        except Exception:
            # Fallback: tıkla + Ctrl+A/Del/yaz
            tc_input.click()
            _bekle(0.1)
            send_keys('^a', pause=0.03)
            send_keys('{DEL}', pause=0.03)
            send_keys(tc, pause=0.02)
            _bekle(0.3)
    except Exception as e:
        _bildir(f'TC yazma hatası: {e}', cb)
        return False

    # Adım 14: Rapor butonu
    try:
        _bildir('Adım 14 — Rapor butonu', cb)
        rapor_btn = doc.getElementById(ID_BUTTON_RAPOR)
        if rapor_btn is None:
            _bildir(f'HATA: {ID_BUTTON_RAPOR} bulunamadı', cb)
            return False
        rapor_btn.click()
        # Sayfa yüklensin — DOM hazır bekleme + ek margin
        _bekle(3.0)
    except Exception as e:
        _bildir(f'Rapor butonu hatası: {e}', cb)
        return False

    # Sayfa değişti → DOM hazır bekle + yeni doc
    doc = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
    if doc is None:
        doc = _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: Raporlar sayfası DOM yok', cb)
        return False

    # Adım 15: Bitmiş Raporları da Göster
    try:
        _bildir('Adım 15 — Bitmiş Raporları da Göster', cb)
        # 10sn'ye kadar polling — buton bazen geç render olur
        bitmis_btn = None
        for _ in range(20):
            try:
                bitmis_btn = doc.getElementById(ID_BUTTON_BITMIS_RAPORLAR)
            except Exception:
                bitmis_btn = None
            if bitmis_btn is not None:
                break
            _bekle(0.5)
            try:
                yeni_doc = _html_doc(medula_hwnd)
                if yeni_doc is not None:
                    doc = yeni_doc
            except Exception:
                pass
        if bitmis_btn is None:
            _bildir(f'UYARI: {ID_BUTTON_BITMIS_RAPORLAR} yok — sadece aktif raporlar', cb)
            # Aktif raporlar yine de okunabilir → True dön
            return True
        bitmis_btn.click()
        # Sayfa yüklensin — DOM hazır bekleme + ek margin
        _bekle(3.0)
        _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb)
        _bildir('✓ Bitmiş raporlar dahil liste açıldı', cb)
        return True
    except Exception as e:
        _bildir(f'Bitmiş Raporları hatası: {e}', cb)
        return False


# ═════════════════════════════════════════════════════════════════════════
# 8. ADIM 17 — Rapor satırlarını oku (tek seferde tüm metadata)
# ═════════════════════════════════════════════════════════════════════════

@dataclass
class _RaporSatirOzet:
    """Liste sayfasından okunan tek satır özeti."""
    sira: int           # tablodaki index (N)
    rapor_takip_no: str
    rapor_tipi: str
    rapor_kodu_metni: str   # raw "06.01 - Hepatit B Gastro(B18.1)"
    rapor_kodu: str         # "06.01"
    tani: str               # "Hepatit B Gastro"
    icd_kodu: str           # "B18.1"
    baslangic_tarihi: str
    bitis_tarihi: str


def rapor_listesini_oku(cb: StatusCb = None) -> List[_RaporSatirOzet]:
    """Adım 17a-d: Rapor listesi tablosundaki tüm satırların metadata'sını
    tek seferde oku (detay sayfalarına girmeden)."""
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        _bildir('HATA: Medula penceresi yok', cb)
        return []
    doc = _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: HTML DOM yok', cb)
        return []

    ozetler: List[_RaporSatirOzet] = []
    try:
        _bildir('Adım 17 — Rapor satırları okunuyor', cb)
        # Her satır id pattern'iyle erişilir; max 200 satır tarayalım
        for i in range(200):
            takip_id = f'{RAPOR_LIST_TEXT_PREFIX}{i}:text14'
            takip_elem = doc.getElementById(takip_id)
            if takip_elem is None:
                break  # daha fazla satır yok
            takip_no = (takip_elem.innerText or '').strip()
            if not takip_no:
                continue
            # Diğer alanlar
            def _txt(suffix: str) -> str:
                try:
                    e = doc.getElementById(f'{RAPOR_LIST_TEXT_PREFIX}{i}:{suffix}')
                    return (e.innerText or '').strip() if e else ''
                except Exception:
                    return ''
            rapor_tipi = _txt('text15')
            kodu_metni = _txt('text96')
            tarih_bas  = _txt('text98')
            tarih_bit  = _txt('text97')

            rapor_kodu, tani, icd = rapor_kodu_metnini_parcala(kodu_metni)

            ozet = _RaporSatirOzet(
                sira=i, rapor_takip_no=takip_no, rapor_tipi=rapor_tipi,
                rapor_kodu_metni=kodu_metni, rapor_kodu=rapor_kodu, tani=tani,
                icd_kodu=icd, baslangic_tarihi=tarih_bas,
                bitis_tarihi=tarih_bit)
            ozetler.append(ozet)
    except Exception as e:
        _bildir(f'Rapor satır okuma hatası: {e}', cb)
        return ozetler

    _bildir(f'✓ {len(ozetler)} rapor satırı tespit edildi', cb)
    return ozetler


def rapor_satirini_ac(sira: int, cb: StatusCb = None) -> bool:
    """Adım 17e: Belirli sıradaki rapor satırına tıkla → detay sayfası."""
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        return False
    doc = _html_doc(medula_hwnd)
    if doc is None:
        return False
    try:
        rowaction_id = f'{RAPOR_LIST_ROWACTION_PREFIX}{sira}:rowActionRaporSec'
        elem = doc.getElementById(rowaction_id)
        if elem is None:
            _bildir(f'HATA: satır {sira} bulunamadı ({rowaction_id})', cb)
            return False
        try:
            elem.click()
        except Exception:
            elem.fireEvent('onclick')
        _bekle(1.5)
        return True
    except Exception as e:
        _bildir(f'Satır tıklama hatası: {e}', cb)
        return False


def rapor_detayini_oku(cb: StatusCb = None) -> str:
    """Adım 18: Rapor detay sayfasının metin içeriğini döndür."""
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        return ''
    doc = _html_doc(medula_hwnd)
    if doc is None:
        return ''
    try:
        body = doc.body
        return (body.innerText or '').strip() if body else ''
    except Exception as e:
        logger.debug(f'detay oku hatası: {e}')
        return ''


def rapor_listesine_geri_don(cb: StatusCb = None) -> bool:
    """Adım 19/20: Geri Dön butonu (rapor detay → liste, liste → reçete)."""
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        return False
    doc = _html_doc(medula_hwnd)
    if doc is None:
        return False
    try:
        geri = doc.getElementById(ID_BUTTON_GERI_DON)
        if geri is None:
            _bildir(f'HATA: {ID_BUTTON_GERI_DON} yok', cb)
            return False
        geri.click()
        _bekle(1.2)
        return True
    except Exception as e:
        _bildir(f'Geri Dön hatası: {e}', cb)
        return False


# ═════════════════════════════════════════════════════════════════════════
# 9. ÜST DÜZEY ENTRY POINT — bir hastanın tüm raporlarını tara + DB'ye yaz
# ═════════════════════════════════════════════════════════════════════════

def hasta_raporlarini_tara_ve_kaydet(
        tc: str,
        kategori_filtre: Optional[str] = None,
        rapor_kodu_filtre: Optional[str] = None,
        detayli_oku: bool = True,
        eos_skip: bool = True,
        cb: StatusCb = None) -> Tuple[int, int]:
    """Bir hasta için tüm raporları (bitmiş dahil) MEDULA'dan tarayıp DB'ye yaz.

    Args:
        tc: 11 haneli hasta TC.
        kategori_filtre: 'HEPATIT_B', 'HEPATIT_C' vb. — sadece bu kategorinin
            raporlarını detaylı oku (None = filtre yok).
        rapor_kodu_filtre: '14.01' / '06.01' vb. — sadece bu rapor koduyla
            başlayan raporları detaylı oku (None = filtre yok). Aktif
            reçetenin rapor koduna göre daraltma için kullanılır.
        detayli_oku: True ise her rapora tek tek girilir + detay_metni
            doldurulur. False ise sadece liste metadata'sı kaydedilir.
        eos_skip: True (default) ise Botanik EOS'ta var olan rapor takip
            no'ları taramada atlanır (CLAUDE.md kuralı: EOS sadece SELECT).
        cb: status callback.

    Returns: (toplam_satir, kaydedilen_satir)
    """
    sema_olustur()  # tablo yoksa oluştur

    _bildir(f'═══ Hasta {tc} rapor taraması başlıyor ═══', cb)

    # 1) Önce aktif Medula penceresi var mı? Varsa öne getir (kullanıcı
    #    kararı 2026-05-25: COM 'Erişim engellendi' hatasını önler).
    on_hwnd = _medula_hwnd_bul()
    if on_hwnd:
        _bildir('[durum] Aktif Medula penceresi bulundu — öne getiriliyor',
                cb)
        _pencereyi_one_getir(on_hwnd, cb=cb)
        _bekle(0.4)

    # State-aware: hangi durumda olduğumuza bakıp uygun adımdan başla
    durum = _medula_durum_tespit(cb=cb)
    _bildir(f'Başlangıç durumu: {durum.value}', cb)

    # Kullanıcı akışı (2026-05-21):
    # 1. Aktif MEDULA + reçete sayfası → direkt TC yapıştır + devam
    # 2. Aktif MEDULA + ana sayfa → reçete listesine tıkla
    # 3. Oturum düşmüş (login.jsp) → 3 kez 1sn aralıkla Giriş butonu
    # 4. Hâlâ açılmazsa → taskkill + yeniden başlat
    # 5. Sayfa düştüyse → Giriş butonuna bas
    # 6. Hiç açık MEDULA yoksa → exe başlat + SifreSorForm login

    # Adım 1 & 2: TC alanı zaten reçete detayda görünür → TC yapıştır
    if durum == MedulaDurum.RECETE_DETAY:
        _bildir('✓ Akış 1: Aktif reçete sayfasında — TC yapıştırılıyor', cb)
        # tc_yaz_ve_raporlari_ac aşağıda durum kontrolünde zaten çağrılacak
    elif durum == MedulaDurum.RAPOR_LISTESI:
        _bildir('✓ Akış 1b: Rapor listesi zaten açık', cb)
    elif durum == MedulaDurum.RECETE_LISTESI:
        _bildir('✓ Akış 2: Reçete listesi açık — 1. satıra tıklanacak', cb)

    # Adım 6: Hiç MEDULA yoksa exe başlat + SifreSorForm login
    elif durum in (MedulaDurum.KAPALI, MedulaDurum.LOGIN_EKRANI,
                       MedulaDurum.LOGIN_DUSTU, MedulaDurum.BILINMEYEN):
        _bildir('Akış 6: MEDULA kapalı/login ekranı → exe + giriş', cb)
        if not medula_baslat_ve_giris(cb=cb):
            return (0, 0)
        durum = _medula_durum_tespit(cb=cb)

    # Adım 3-5: Oturum düşmüş (IE login.jsp) → 3 kez Giriş butonu →
    # başaramazsa taskkill + tam yenile
    if durum == MedulaDurum.ANA_SAYFA_LOGIN_GEREK:
        _bildir('Akış 3: Oturum düşmüş (login.jsp) — Giriş butonu 3 deneme',
                cb)
        main_hwnd = _medula_hwnd_bul()
        basarili = False
        if main_hwnd:
            basarili = _medulaya_3_kez_giris_dene(main_hwnd, cb=cb)
        if not basarili:
            # Adım 4: 3 deneme başarısız → taskkill + tam yenile
            _bildir('Akış 4: 3 deneme başarısız — taskkill + temiz başlat', cb)
            _medula_taskkill(cb=cb)
            if not medula_baslat_ve_giris(cb=cb, taskkill_recovery=False):
                return (0, 0)
            durum = _medula_durum_tespit(cb=cb)
            # Hâlâ login.jsp'deyse son bir Giriş butonu denemesi
            if durum == MedulaDurum.ANA_SAYFA_LOGIN_GEREK:
                main_hwnd = _medula_hwnd_bul()
                if main_hwnd:
                    _medulaya_3_kez_giris_dene(main_hwnd, cb=cb)
                    durum = _medula_durum_tespit(cb=cb)
        else:
            durum = _medula_durum_tespit(cb=cb)

    # Adım 8-9: Reçete listesi B grubu — başarısızsa taskkill recovery
    if durum == MedulaDurum.ANA_SAYFA:
        if not recete_listesi_b_grubu_ac(cb=cb):
            _bildir('Reçete Listesi açılamadı — taskkill ile tam yenile', cb)
            _medula_taskkill(cb=cb)
            if not medula_baslat_ve_giris(cb=cb, taskkill_recovery=False):
                return (0, 0)
            durum2 = _medula_durum_tespit(cb=cb)
            if durum2 == MedulaDurum.ANA_SAYFA_LOGIN_GEREK:
                main_hwnd = _medula_hwnd_bul()
                if main_hwnd:
                    _medulaya_3_kez_giris_dene(main_hwnd, cb=cb)
            if not recete_listesi_b_grubu_ac(cb=cb):
                _bildir('Reçete Listesi 2. denemede de açılamadı', cb)
                return (0, 0)
        durum = MedulaDurum.RECETE_LISTESI

    # Adım 11: 1. reçete satırı (TC alanına ulaşmak için herhangi bir reçete
    # açılmalı). Zaten reçete detayında / rapor listesindeysek atlanır.
    if durum == MedulaDurum.RECETE_LISTESI:
        if not ilk_recete_satirini_ac(cb=cb):
            return (0, 0)
        durum = MedulaDurum.RECETE_DETAY

    # Adım 12-15: TC + Rapor + Bitmiş (rapor listesinde değilsek)
    if durum == MedulaDurum.RECETE_DETAY:
        if not tc_yaz_ve_raporlari_ac(tc, cb=cb):
            return (0, 0)
        durum = MedulaDurum.RAPOR_LISTESI
    elif durum == MedulaDurum.RAPOR_LISTESI:
        _bildir('Rapor listesi zaten açık — TC yazma atlanıyor', cb)

    # Adım 17: Rapor listesi metadata
    ozetler = rapor_listesini_oku(cb=cb)
    if not ozetler:
        _bildir('Hastanın MEDULA\'da raporu yok', cb)
        return (0, 0)

    mevcut_takipler = mevcut_rapor_takipleri(tc)
    _bildir(f'DB\'de zaten kayıtlı: {len(mevcut_takipler)} rapor', cb)

    # EOS skip: Botanik EOS'taki rapor takip no'larını al → yerel set ile
    # birleştir. EOS'ta var olan rapor için tekrar Medula detay sayfasını
    # açmıyoruz (kullanıcı kararı 2026-05-25). CLAUDE.md: salt SELECT.
    eos_takipler: set = set()
    if eos_skip:
        try:
            from botanik_db import get_botanik_db
            db = get_botanik_db()
            if db.baglan():
                eos_takipler = db.hasta_tum_rapor_takip_nolari(tc)
                _bildir(f'EOS\'ta zaten kayıtlı: {len(eos_takipler)} rapor',
                        cb)
        except Exception as e:
            _bildir(f'UYARI: EOS skip listesi alınamadı: {e}', cb)
    skip_takipler = mevcut_takipler | eos_takipler

    kaydedilen = 0
    for ozet in ozetler:
        # Yerel DB veya EOS'ta varsa atla
        if ozet.rapor_takip_no in skip_takipler:
            kaynak = ('yerel+EOS' if ozet.rapor_takip_no in mevcut_takipler
                       and ozet.rapor_takip_no in eos_takipler
                       else 'EOS' if ozet.rapor_takip_no in eos_takipler
                       else 'yerel')
            _bildir(
                f'  ↺ Atlandı ({kaynak}): {ozet.rapor_takip_no} '
                f'({ozet.rapor_kodu})', cb)
            continue

        kayit = RaporKaydi(
            hasta_tc=tc,
            rapor_takip_no=ozet.rapor_takip_no,
            baslangic_tarihi=ozet.baslangic_tarihi,
            bitis_tarihi=ozet.bitis_tarihi,
            rapor_kodu=ozet.rapor_kodu,
            tani=ozet.tani,
            icd_kodu=ozet.icd_kodu,
            rapor_tipi=ozet.rapor_tipi,
            rapor_sira=ozet.sira,
        )
        kayit.kategori = kayit.kategoriyi_belirle()

        # Filtreler: kategori VE rapor_kodu eşleşmesi (verilenler için)
        kategori_uyumlu = (kategori_filtre is None
                           or kayit.kategori == kategori_filtre)
        # Rapor kodu prefix eşleşmesi — '14.01' filtre, '14.01.02' eşleşir
        rapor_kodu_uyumlu = (rapor_kodu_filtre is None
                              or kayit.rapor_kodu.startswith(rapor_kodu_filtre))

        if detayli_oku and kategori_uyumlu and rapor_kodu_uyumlu:
            # Adım 17e: Satıra tıkla → detay aç → metni oku → geri dön
            _bildir(f'  ▶ Detay açılıyor: {ozet.rapor_takip_no} ({ozet.rapor_kodu})', cb)
            if rapor_satirini_ac(ozet.sira, cb=cb):
                kayit.detay_metni = rapor_detayini_oku(cb=cb)[:8000]   # ilk 8KB
                rapor_listesine_geri_don(cb=cb)
        else:
            # Filtre eşleşmedi — sadece metadata kaydet, detayı atla
            sebep_p = []
            if not kategori_uyumlu:
                sebep_p.append(f'kategori≠{kategori_filtre}')
            if not rapor_kodu_uyumlu:
                sebep_p.append(f'kod≠{rapor_kodu_filtre}')
            if sebep_p:
                _bildir(
                    f'  ▷ Metadata-only: {ozet.rapor_takip_no} '
                    f'({ozet.rapor_kodu}) — {", ".join(sebep_p)}', cb)

        try:
            kaydet(kayit)
            kaydedilen += 1
            _bildir(f'  ✓ Kaydedildi: {ozet.rapor_kodu_metni} ({ozet.baslangic_tarihi})', cb)
        except Exception as e:
            _bildir(f'  ✗ Kayıt hatası ({ozet.rapor_takip_no}): {e}', cb)

    _bildir(f'═══ Tamamlandı: {len(ozetler)} satır, {kaydedilen} yeni kayıt ═══', cb)
    return (len(ozetler), kaydedilen)


# ═════════════════════════════════════════════════════════════════════════
# 10. DEBUG — HTML dump (Adım 11 ilk başarılı tıklama sonrası)
# ═════════════════════════════════════════════════════════════════════════

def _debug_html_dump(doc, dosya_adi: str, cb: StatusCb = None) -> None:
    """Sayfa HTML'ini APPDATA/BotanikKasa/debug/ altına yaz (sonraki
    versiyon için kesin id'leri öğrenmek üzere)."""
    try:
        appdata = os.environ.get('APPDATA')
        if not appdata:
            return
        debug_dir = Path(appdata) / 'BotanikKasa' / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
        path = debug_dir / dosya_adi
        try:
            html = doc.body.outerHTML
        except Exception:
            html = doc.documentElement.outerHTML
        path.write_text(html, encoding='utf-8', errors='ignore')
        _bildir(f'[debug] HTML dump: {path}', cb)
    except Exception as e:
        logger.debug(f'HTML dump hatası: {e}')


# Public API
__all__ = [
    'MedulaDurum',
    'medula_baslat_ve_giris',
    'recete_listesi_b_grubu_ac',
    'ilk_recete_satirini_ac',
    'tc_yaz_ve_raporlari_ac',
    'rapor_listesini_oku',
    'rapor_satirini_ac',
    'rapor_detayini_oku',
    'rapor_listesine_geri_don',
    'hasta_raporlarini_tara_ve_kaydet',
]
