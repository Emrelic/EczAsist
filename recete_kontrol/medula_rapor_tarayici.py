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
LOGIN_TITLE                = 'BotanikEOS'    # contains
ANASAYFA_TITLE             = 'MEDULA'        # contains
COMBO_KULLANICI            = 'cmbKullanicilar'
EDIT_SIFRE                 = 'txtSifre'
BUTTON_GIRIS               = 'btnGirisYap'
KULLANICI_VARSAYILAN       = 'botan'
SIFRE_VARSAYILAN           = '152634'

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
SATIR_YUKSEKLIK_DP       = 30   # 'başlık + 30dp altı' fallback

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
    KAPALI         = 'kapali'
    LOGIN_EKRANI   = 'login_ekrani'
    LOGIN_DUSTU    = 'login_dustu'
    ANA_SAYFA      = 'ana_sayfa'
    RECETE_LISTESI = 'recete_listesi'
    RECETE_DETAY   = 'recete_detay'
    RAPOR_LISTESI  = 'rapor_listesi'
    BILINMEYEN     = 'bilinmeyen'


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
    """MEDULA ana penceresinin HWND'sini bul."""
    try:
        from pencere_yerlesim import _medula_hwnd_bul as _bul
        return _bul()
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


def _html_doc(medula_hwnd: Optional[int] = None):
    """MEDULA IE_Server'ında IHTMLDocument2 proxy döndür."""
    try:
        from medula_html_dom import html_doc_bul
        return html_doc_bul(medula_hwnd)
    except Exception as e:
        logger.warning(f'html_doc_bul hatası: {e}')
        return None


def _bekle(saniye: float = 0.5) -> None:
    time.sleep(saniye)


# ═════════════════════════════════════════════════════════════════════════
# 3b. PROCESS / LOGIN PENCERESİ YARDIMCILARI
# ═════════════════════════════════════════════════════════════════════════

def _login_hwnd_bul() -> Optional[int]:
    """Login penceresinin HWND'sini bul (BotanikEOS başlıklı, MEDULA değil)."""
    try:
        import win32gui
        bulunan = [None]

        def _enum(h, _):
            try:
                t = win32gui.GetWindowText(h) or ''
                # MEDULA ana sayfayı dışla, sadece login (BotanikEOS)
                if (LOGIN_TITLE in t and ANASAYFA_TITLE not in t
                        and win32gui.IsWindowVisible(h)):
                    bulunan[0] = h
                    return False
            except Exception:
                pass
            return True

        win32gui.EnumWindows(_enum, None)
        return bulunan[0]
    except Exception:
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

    # 4. Ana sayfa açık — içeride hangi sayfa?
    doc = _html_doc(main_hwnd)
    if doc is None:
        _bildir('[durum] HTML DOM okunamıyor → ANA_SAYFA (fallback)', cb)
        return MedulaDurum.ANA_SAYFA

    # 4a. Reçete detayında TC alanı var mı?
    try:
        if doc.getElementById(ID_TC_INPUT) is not None:
            _bildir('[durum] TC alanı (f:t18) görünür → RECETE_DETAY', cb)
            return MedulaDurum.RECETE_DETAY
    except Exception:
        pass

    # 4b. Rapor listesi açık mı? (text14 = ilk rapor takip no)
    try:
        if doc.getElementById(f'{RAPOR_LIST_TEXT_PREFIX}0:text14') is not None:
            _bildir('[durum] Rapor takip no görünür → RAPOR_LISTESI', cb)
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

def _combo_kullanici_sec(combo, kullanici: str, send_keys,
                            cb: StatusCb = None) -> bool:
    """ComboBox'tan kullanıcıyı seç — 3 strateji.

    Strateji 1: pywinauto select(kullanici) — DropDownList için ideal
    Strateji 2: ComboBox'a tıkla + dropdown'dan klavye ile seç (down/up + Enter)
    Strateji 3: Doğrudan edit alanına yaz (DropDown editable için)
    """
    # Strateji 1: select() — DropDownList için en güvenilir
    try:
        items = combo.item_texts() if hasattr(combo, 'item_texts') else []
        _bildir(f'  Combobox item\'ları: {items}', cb)
        # Tam eşleşme veya küçük harfli eşleşme
        eslesen = None
        for it in items:
            if it and it.strip().lower() == kullanici.lower():
                eslesen = it
                break
        if eslesen is None:
            for it in items:
                if it and kullanici.lower() in it.strip().lower():
                    eslesen = it
                    break
        if eslesen:
            try:
                combo.select(eslesen)
                _bekle(0.3)
                _bildir(f'  ✓ Strateji 1: select("{eslesen}")', cb)
                return True
            except Exception as e:
                logger.debug(f'select() hatası: {e}')
    except Exception as e:
        logger.debug(f'item_texts hatası: {e}')

    # Strateji 2: tıkla + klavye nav (dropdown aç → typeahead/arrow → Enter)
    try:
        combo.click_input()
        _bekle(0.3)
        # Typeahead: kullanıcı adının ilk harfini yaz (b → "botan" bulunur)
        send_keys(kullanici[0].lower(), pause=0.1)
        _bekle(0.2)
        send_keys('{ENTER}', pause=0.1)
        _bekle(0.4)
        _bildir(f'  ✓ Strateji 2: typeahead "{kullanici[0]}" + Enter', cb)
        return True
    except Exception as e:
        logger.debug(f'Strateji 2 hatası: {e}')

    # Strateji 3: editable combobox — doğrudan yaz
    try:
        combo.click_input()
        _bekle(0.2)
        send_keys('^a', pause=0.05)
        send_keys('{DEL}', pause=0.05)
        send_keys(kullanici, pause=0.06)
        _bekle(0.2)
        send_keys('{ENTER}', pause=0.1)
        _bekle(0.3)
        _bildir(f'  ✓ Strateji 3: edit + yaz "{kullanici}"', cb)
        return True
    except Exception as e:
        _bildir(f'  ✗ Tüm stratejiler başarısız: {e}', cb)
        return False


def medula_baslat_ve_giris(kullanici: str = KULLANICI_VARSAYILAN,
                              sifre: str = SIFRE_VARSAYILAN,
                              exe_path: str = MEDULA_EXE_PATH,
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

    # State tespit
    durum = _medula_durum_tespit(cb=cb)
    if durum in (MedulaDurum.ANA_SAYFA, MedulaDurum.RECETE_LISTESI,
                 MedulaDurum.RECETE_DETAY, MedulaDurum.RAPOR_LISTESI):
        _bildir(f'✓ Medula zaten açık ({durum.value}) — giriş atlanıyor', cb)
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
            _bildir(f'HATA: exe bulunamadı: {exe_path}', cb)
            return False
        try:
            subprocess.Popen([exe_path], shell=False)
        except Exception as e:
            _bildir(f'HATA: exe başlatılamadı: {e}', cb)
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

    # Şimdi login penceresinde olmalıyız (LOGIN_EKRANI ya da yeni başlatıldı)
    if not _login_hwnd_bul():
        _bildir('HATA: Login penceresi bulunamadı', cb)
        return False

    # Login app'e bağlan
    login_app = None
    for _ in range(10):
        try:
            login_app = Application(backend='uia').connect(
                title_re=f'.*{LOGIN_TITLE}.*', timeout=2)
            break
        except Exception:
            _bekle(0.4)
            continue
    if not login_app:
        _bildir('HATA: Login app\'e bağlanılamadı', cb)
        return False

    try:
        login_win = login_app.window(title_re=f'.*{LOGIN_TITLE}.*')
        # Pencereyi öne getir — focus garanti
        try:
            login_win.set_focus()
            _bekle(0.3)
        except Exception:
            pass

        # Adım 3-4: cmbKullanicilar → kullanıcı seç (3 stratejili)
        _bildir(f'Kullanıcı seçiliyor: {kullanici}', cb)
        combo = login_win.child_window(auto_id=COMBO_KULLANICI,
                                          control_type='ComboBox')
        combo.wait('visible', timeout=5)
        if not _combo_kullanici_sec(combo, kullanici, send_keys, cb=cb):
            _bildir('HATA: Kullanıcı seçilemedi (3 strateji başarısız)', cb)
            return False

        # Adım 5: txtSifre → şifre (set_text + send_keys fallback)
        _bildir('Şifre giriliyor', cb)
        sifre_edit = login_win.child_window(auto_id=EDIT_SIFRE,
                                              control_type='Edit')
        sifre_edit.wait('visible', timeout=5)
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
        giris_btn.wait('enabled', timeout=5)
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
    while time.time() - bekleme_basla < 30:
        _bekle(0.5)
        if _medula_hwnd_bul():
            _bildir('✓ MEDULA ana sayfa hazır', cb)
            return True
        # Login hala açık ama uzun sürüyor → donma olabilir
        if (time.time() - bekleme_basla > LOGIN_DONMA_ESIK_SN
                and _login_hwnd_bul()):
            break

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
    """Adım 8-9b: Sol menü Reçete Listesi → B grubu → Sorgula."""
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        _bildir('HATA: Medula penceresi bulunamadı', cb)
        return False

    doc = _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: HTML DOM proxy alınamadı', cb)
        return False

    # Adım 8: Sol menü Reçete Listesi
    try:
        _bildir('Sol menü → Reçete Listesi', cb)
        elem = doc.getElementById(ID_MENU_RECETE_LISTESI)
        if elem is None:
            _bildir(f'HATA: {ID_MENU_RECETE_LISTESI} bulunamadı', cb)
            return False
        elem.click()
        _bekle(1.5)   # sayfa yüklenme bekle
    except Exception as e:
        _bildir(f'Reçete Listesi tıklama hatası: {e}', cb)
        return False

    # Sayfa değişti — yeni doc al
    doc = _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: Reçete Listesi sayfası DOM yok', cb)
        return False

    # Adım 9: B grubu — TD[veri="4"]
    try:
        _bildir('B grubu seçiliyor', cb)
        # querySelector kullan (IE eski sürümde sıkıntı olabilir, fallback de var)
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
        b_td.click()
        _bekle(0.5)
    except Exception as e:
        _bildir(f'B grubu tıklama hatası: {e}', cb)
        return False

    # Adım 9b: Sorgula
    try:
        _bildir('Sorgula', cb)
        sorgula_btn = doc.getElementById(ID_BUTTON_SORGULA_B_GRUBU)
        if sorgula_btn is None:
            _bildir(f'HATA: {ID_BUTTON_SORGULA_B_GRUBU} bulunamadı', cb)
            return False
        sorgula_btn.click()
        _bekle(2.0)  # liste yüklenme
        _bildir('✓ Reçete listesi (B grubu) açıldı', cb)
        return True
    except Exception as e:
        _bildir(f'Sorgula tıklama hatası: {e}', cb)
        return False


# ═════════════════════════════════════════════════════════════════════════
# 6. ADIM 11 — Reçete listesi 1. satır seç (3 katmanlı fallback)
# ═════════════════════════════════════════════════════════════════════════

def ilk_recete_satirini_ac(cb: StatusCb = None) -> bool:
    """Adım 11: Reçete listesindeki 1. satıra tıkla → reçete detay sayfası.

    3 katmanlı fallback:
        1. MSHTML DOM scan: rowClass1/rowClass2 + cursor:pointer TR
        2. Pattern guess: bilinen form1:tableExReceteList:0:... id'leri
        3. 'Sıra' başlık elementinin altına 30dp element-relative click_input
    """
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        _bildir('HATA: Medula penceresi yok', cb)
        return False

    doc = _html_doc(medula_hwnd)

    # ── Katman 1: DOM scan ──
    if doc is not None:
        try:
            _bildir('Adım 11 — Katman 1: DOM scan (rowClass1/2)', cb)
            rows = None
            for cls in ('rowClass1', 'rowClass2'):
                try:
                    rs = doc.getElementsByClassName(cls)
                    if rs and rs.length > 0:
                        rows = rs
                        break
                except Exception:
                    continue
            if rows and rows.length > 0:
                ilk = rows.item(0)
                # Reçete listesi sayfası HTML'i debug için dump et
                _debug_html_dump(doc, 'recete_listesi.html', cb)
                try:
                    ilk.click()
                except Exception:
                    ilk.fireEvent('onclick')
                _bekle(1.5)
                _bildir('✓ 1. satır tıklandı (DOM scan)', cb)
                return True
        except Exception as e:
            logger.debug(f'Katman 1 hatası: {e}')

    # ── Katman 2: Pattern guess ──
    if doc is not None:
        try:
            _bildir('Adım 11 — Katman 2: pattern guess', cb)
            for pid in RECETE_LIST_PATTERN_TAHMINLER:
                try:
                    elem = doc.getElementById(pid)
                    if elem is not None:
                        elem.click()
                        _bekle(1.5)
                        _bildir(f'✓ 1. satır tıklandı (pattern: {pid})', cb)
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f'Katman 2 hatası: {e}')

    # ── Katman 3: Başlık + 30dp altı element-relative ──
    return _ilk_satir_baslik_fallback(medula_hwnd, cb)


def _ilk_satir_baslik_fallback(medula_hwnd: int, cb: StatusCb = None) -> bool:
    """Katman 3: 'Sıra' başlık Text elementinin altına 30dp tıkla
    (element-relative, mutlak ekran koord. değil)."""
    Application, Desktop, send_keys = _pywinauto_yukle()
    try:
        _bildir('Adım 11 — Katman 3: başlık+30dp fallback', cb)
        app = Application(backend='uia').connect(handle=medula_hwnd, timeout=3)
        win = app.window(handle=medula_hwnd)
        baslik = win.descendants(title=RECETE_TABLO_BASLIK_TEXT,
                                   control_type='Text')
        if not baslik:
            _bildir(f'HATA: "{RECETE_TABLO_BASLIK_TEXT}" başlık elementi yok', cb)
            return False
        h = baslik[0]
        rect = h.rectangle()
        # Element-içi koord: (width/2, height + 30dp)
        x_in = rect.width() // 2
        y_in = rect.height() + SATIR_YUKSEKLIK_DP
        try:
            h.click_input(coords=(x_in, y_in))
            _bekle(1.5)
            _bildir(f'✓ Başlık altı +{SATIR_YUKSEKLIK_DP}dp tıklandı', cb)
            return True
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

    doc = _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: HTML DOM proxy yok', cb)
        return False

    # Adım 12-13: TC alanı temizle + yaz
    try:
        _bildir(f'Adım 12 — TC alanına {tc} yazılıyor', cb)
        tc_input = doc.getElementById(ID_TC_INPUT)
        if tc_input is None:
            _bildir(f'HATA: {ID_TC_INPUT} bulunamadı', cb)
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
        _bekle(2.0)
    except Exception as e:
        _bildir(f'Rapor butonu hatası: {e}', cb)
        return False

    # Sayfa değişti → yeni doc
    doc = _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: Raporlar sayfası DOM yok', cb)
        return False

    # Adım 15: Bitmiş Raporları da Göster
    try:
        _bildir('Adım 15 — Bitmiş Raporları da Göster', cb)
        bitmis_btn = doc.getElementById(ID_BUTTON_BITMIS_RAPORLAR)
        if bitmis_btn is None:
            # Bu buton bazen hemen görünmeyebilir, bir saniye bekle ve tekrar dene
            _bekle(1.0)
            doc = _html_doc(medula_hwnd)
            bitmis_btn = doc.getElementById(ID_BUTTON_BITMIS_RAPORLAR) if doc else None
        if bitmis_btn is None:
            _bildir(f'UYARI: {ID_BUTTON_BITMIS_RAPORLAR} yok — sadece aktif raporlar', cb)
            # Aktif raporlar yine de okunabilir → True dön
            return True
        bitmis_btn.click()
        _bekle(2.0)
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
        detayli_oku: bool = True,
        cb: StatusCb = None) -> Tuple[int, int]:
    """Bir hasta için tüm raporları (bitmiş dahil) MEDULA'dan tarayıp DB'ye yaz.

    Args:
        tc: 11 haneli hasta TC.
        kategori_filtre: 'HEPATIT_B', 'HEPATIT_C' vb. — sadece bu kategorinin
            raporlarını detaylı oku (None = hepsini detaylı oku).
        detayli_oku: True ise her rapora tek tek girilir + detay_metni doldurulur.
            False ise sadece liste metadata'sı kaydedilir (hızlı).

    Returns: (toplam_satir, kaydedilen_satir)
    """
    sema_olustur()  # tablo yoksa oluştur

    _bildir(f'═══ Hasta {tc} rapor taraması başlıyor ═══', cb)

    # State-aware: hangi durumda olduğumuza bakıp uygun adımdan başla
    durum = _medula_durum_tespit(cb=cb)
    _bildir(f'Başlangıç durumu: {durum.value}', cb)

    # Adım 1-7: Login (gerekiyorsa)
    if durum in (MedulaDurum.KAPALI, MedulaDurum.LOGIN_EKRANI,
                 MedulaDurum.LOGIN_DUSTU, MedulaDurum.BILINMEYEN):
        if not medula_baslat_ve_giris(cb=cb):
            return (0, 0)
        durum = MedulaDurum.ANA_SAYFA  # login başarılı

    # Adım 8-9: Reçete listesi B grubu (zaten reçete detay/rapor listesinde
    # değilsek)
    if durum == MedulaDurum.ANA_SAYFA:
        if not recete_listesi_b_grubu_ac(cb=cb):
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

    kaydedilen = 0
    for ozet in ozetler:
        # Mevcutsa atla (idempotent çalışsın)
        if ozet.rapor_takip_no in mevcut_takipler:
            _bildir(f'  ↺ Atlandı (zaten kayıtlı): {ozet.rapor_takip_no}', cb)
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

        # Kategori filtresi varsa, başka kategoriyi sadece metadata olarak kaydet
        kategori_uyumlu = (kategori_filtre is None
                           or kayit.kategori == kategori_filtre)

        if detayli_oku and kategori_uyumlu:
            # Adım 17e: Satıra tıkla → detay aç → metni oku → geri dön
            _bildir(f'  ▶ Detay açılıyor: {ozet.rapor_takip_no} ({ozet.rapor_kodu})', cb)
            if rapor_satirini_ac(ozet.sira, cb=cb):
                kayit.detay_metni = rapor_detayini_oku(cb=cb)[:8000]   # ilk 8KB
                rapor_listesine_geri_don(cb=cb)

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
