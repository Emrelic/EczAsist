# -*- coding: utf-8 -*-
"""Medula — Hasta İlaç Geçmişi canlı tarayıcı (SADECE OKUMA + navigasyon).

Akış (kullanıcı onayı 2026-07-04, canlı doğrulandı):
  Ana menü → Reçete Listesi → en üstteki reçeteyi aç → TC alanını (f:t18)
  temizle + hedef hastanın TC'sini yaz → "İlaç" (f:buttonIlacListesi) →
  "Kullanılan İlaç Listesi" tablosunu (tableExKisiIlacList) TÜM SAYFALARIYLA oku
  → "Geri Dön".

Bu ekran hastanın SGK'daki çapraz-reçete ilaç geçmişini verir (başka
eczanelerdeki reçeteler dahil) — Botanik EOS'tan zengin: her ilaç için
Rap. Teşhisi + Rapor Takip No + ATC id.

⚠️ SAYFALAMA TUZAĞI (canlı keşif): satır index'leri sayfalar arası GLOBAL'dir.
Sayfa 1 = index 0..19, sayfa 2 = index 20..37 (0'dan başlamaz). Pager JSF
postback'i `fireEvent('onclick')` ile tetiklenir; yeni sayfanın ilk satırı
(prev_max+1) DOM'a gelene kadar beklenir.

⚠️ KIRMIZI ÇİZGİ: Bu modül Medula'ya YAZMAZ. Sadece f:t18'e sorgu TC'si yazıp
(veri değiştirmez) görüntüleme butonlarına basar ve metin okur.

Ana giriş: ``ilac_gecmisini_oku(tc)`` → ``List[Dict]``.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Callable

from recete_kontrol.medula_rapor_tarayici import (
    _medula_hwnd_bul, _html_doc, _html_dom_hazir_bekle, _pywinauto_yukle,
    _bildir, _bekle, ID_TC_INPUT, ID_BUTTON_GERI_DON,
)

StatusCb = Optional[Callable[[str], None]]

# ─── Element ID'leri (canlı HTML'den teyit — 2026-07-04) ────────────────────
ID_BUTTON_ILAC = 'f:buttonIlacListesi'
ILAC_TID = 'form1:tableExKisiIlacList'
# Satır hücre sonekleri
_HUCRE = {
    'recete_no':      'text14',
    'ilac_adi':       'text15',   # ayrıca atcid attribute'u var
    'recete_tarihi':  'text10',
    'ilac_alim_tar':  'text21',
    'verilebilecegi': 'text13',
    'adet':           'text18',
    'kullanim':       'text17',
    'teshis_raptak':  'text26',   # "04.02.1 - 563346525" (rap teşhis - rap takip no)
}


# ─── DOM yardımcıları ───────────────────────────────────────────────────────

def _val(doc, eid: str) -> Optional[str]:
    try:
        e = doc.getElementById(eid)
        return (getattr(e, 'innerText', '') or '').strip() if e is not None else None
    except Exception:
        return None


def _attr(doc, eid: str, ad: str) -> Optional[str]:
    try:
        e = doc.getElementById(eid)
        return e.getAttribute(ad) if e is not None else None
    except Exception:
        return None


def _elem_tikla(doc, eid: str) -> bool:
    """JSF onclick postback'ini tetikle (pager/buton). Yalnız görüntüleme."""
    e = doc.getElementById(eid)
    if e is None:
        return False
    for yontem in ('fireEvent', 'click', 'exec'):
        try:
            if yontem == 'fireEvent':
                e.fireEvent('onclick')
            elif yontem == 'click':
                e.click()
            else:
                doc.parentWindow.execScript(
                    "document.getElementById('%s').click()" % eid, 'JavaScript')
            return True
        except Exception:
            continue
    return False


def _pager_idx(doc) -> int:
    v = _attr(doc, f'{ILAC_TID}:web1__pagerWeb', 'value')
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _sonraki_sayfa_link(doc, hedef_no: int) -> Optional[str]:
    """innerText == str(hedef_no) olan numaralı pager linkinin id'si."""
    for i in range(25):
        eid = f'{ILAC_TID}:web1__pagerWeb__{i}'
        e = doc.getElementById(eid)
        if e is None:
            continue
        try:
            txt = (getattr(e, 'innerText', '') or '').strip()
        except Exception:
            txt = ''
        if txt == str(hedef_no):
            return eid
    return None


# ─── TC yazma (rapor tarayıcı kalıbı) ───────────────────────────────────────

def _tc_yaz(doc, medula_hwnd: int, tc: str, cb: StatusCb = None) -> bool:
    """f:t18 alanını temizleyip hedef TC'yi yaz (DOM value + onchange,
    fallback click+Ctrl+A/Del/yaz). Reçete/rapor verisini DEĞİŞTİRMEZ —
    yalnız sorgulama alanı."""
    _, _, send_keys = _pywinauto_yukle()
    tc_input = None
    for _ in range(30):
        try:
            tc_input = doc.getElementById(ID_TC_INPUT)
        except Exception:
            tc_input = None
        if tc_input is not None:
            break
        _bekle(0.5)
        try:
            yeni = _html_doc(medula_hwnd)
            if yeni is not None:
                doc = yeni
        except Exception:
            pass
    if tc_input is None:
        _bildir(f'HATA: {ID_TC_INPUT} bulunamadı (15sn polling)', cb)
        return False
    try:
        tc_input.value = tc
        tc_input.focus()
        try:
            tc_input.fireEvent('onchange')
        except Exception:
            pass
        _bekle(0.3)
    except Exception:
        try:
            tc_input.click()
            _bekle(0.1)
            send_keys('^a', pause=0.03)
            send_keys('{DEL}', pause=0.03)
            send_keys(tc, pause=0.02)
            _bekle(0.3)
        except Exception as e:
            _bildir(f'TC yazma hatası: {e}', cb)
            return False
    return True


# ─── Tablo okuma ────────────────────────────────────────────────────────────

def _sayfadaki_satirlar(doc) -> Dict[int, Dict]:
    """Mevcut sayfadaki satırları GLOBAL index ile oku (sayfa 2 = 20+).
    40 ardışık boş index sonrası durur (sayfa sonu)."""
    rows: Dict[int, Dict] = {}
    miss = 0
    n = 0
    while n < 600 and miss < 40:
        rn = _val(doc, f'{ILAC_TID}:{n}:{_HUCRE["recete_no"]}')
        if rn is None:
            miss += 1
            n += 1
            continue
        miss = 0
        kayit = {'idx': n}
        for alan, sonek in _HUCRE.items():
            kayit[alan] = _val(doc, f'{ILAC_TID}:{n}:{sonek}')
        kayit['atc_id'] = _attr(doc, f'{ILAC_TID}:{n}:{_HUCRE["ilac_adi"]}', 'atcid')
        kayit['recete_no'] = rn
        kayit['kaynak'] = 'medula'
        rows[n] = kayit
        n += 1
    return rows


def _tum_sayfalari_oku(cb: StatusCb = None, max_sayfa: int = 15) -> List[Dict]:
    """İlaç listesi ekranı açıkken tüm sayfaları gezerek satırları oku."""
    tum: Dict[int, Dict] = {}
    d = _html_doc(_medula_hwnd_bul())
    if d is None:
        _bildir('HATA: HTML DOM proxy yok (ilaç listesi)', cb)
        return []
    sayfa = _pager_idx(d) + 1
    for _ in range(max_sayfa):
        rows = _sayfadaki_satirlar(d)
        tum.update(rows)
        _bildir(f'İlaç geçmişi sayfa {sayfa}: {len(rows)} satır '
                f'(kümülatif {len(tum)})', cb)
        nx = _sonraki_sayfa_link(d, sayfa + 1)
        if not nx:
            break
        beklenen = (max(tum) + 1) if tum else 0
        _elem_tikla(d, nx)
        # yeni sayfanın ilk satırı DOM'a gelene kadar bekle
        for _p in range(30):
            _bekle(0.4)
            d = _html_doc(_medula_hwnd_bul())
            if d is not None and _val(d, f'{ILAC_TID}:{beklenen}:{_HUCRE["recete_no"]}') is not None:
                break
        sayfa = _pager_idx(d) + 1
    return [tum[k] for k in sorted(tum)]


# ─── Ana giriş ──────────────────────────────────────────────────────────────

def ilac_gecmisini_oku(tc: str, cb: StatusCb = None,
                       geri_don: bool = True) -> List[Dict]:
    """Reçete DETAY ekranı açıkken (f:t18 görünür): TC yaz → İlaç → tüm
    sayfaları oku → Geri Dön. Hastanın SGK ilaç geçmişini döndürür.

    Ön koşul: Medula reçete detay ekranında olmalı (recete_listesi_b_grubu_ac
    + ilk_recete_satirini_ac ile gelinir). Kombine akış için
    `hasta_ilac_gecmisi` kullan.

    Returns: List[Dict] — her ilaç: recete_no, ilac_adi, atc_id, tarihler,
    adet, kullanim, teshis_raptak, kaynak='medula'. Hata/veri yoksa [].
    """
    if not tc or not (len(tc) == 11 and tc.isdigit()):
        _bildir(f'HATA: Geçersiz TC: {tc!r}', cb)
        return []
    medula_hwnd = _medula_hwnd_bul()
    if not medula_hwnd:
        _bildir('HATA: Medula penceresi yok', cb)
        return []
    doc = _html_dom_hazir_bekle(medula_hwnd, sure_sn=10.0, cb=cb) \
        or _html_doc(medula_hwnd)
    if doc is None:
        _bildir('HATA: HTML DOM proxy yok', cb)
        return []

    _bildir(f'İlaç geçmişi: TC {tc[:3]}****{tc[-1]} yazılıyor', cb)
    if not _tc_yaz(doc, medula_hwnd, tc, cb):
        return []

    _bildir('İlaç butonu (f:buttonIlacListesi)', cb)
    if not _elem_tikla(doc, ID_BUTTON_ILAC):
        _bildir('HATA: İlaç butonu tıklanamadı', cb)
        return []

    # İlaç listesi yüklensin (row0 gelene kadar bekle)
    for _ in range(30):
        _bekle(0.4)
        d = _html_doc(medula_hwnd)
        if d is not None and _val(d, f'{ILAC_TID}:0:{_HUCRE["recete_no"]}') is not None:
            break

    sonuc = _tum_sayfalari_oku(cb)

    if geri_don:
        try:
            d = _html_doc(medula_hwnd)
            _elem_tikla(d, ID_BUTTON_GERI_DON)
            _bekle(0.8)
        except Exception:
            pass

    _bildir(f'İlaç geçmişi: {len(sonuc)} kayıt okundu', cb)
    return sonuc
