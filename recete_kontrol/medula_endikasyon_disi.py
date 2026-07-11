# -*- coding: utf-8 -*-
"""Medula — Endikasyon Dışı İzin ("End.Dışı (Yeni)") canlı tarayıcı.

Reçete detay ekranındaki `f:buttonKisiEndikasyonDisiSorgu` butonu hastanın
endikasyon dışı ilaç kullanım İZİNLERİNİ listeler
(KisiEndikasyonDisiIzinIslem.jsp). Her satıra tıklanınca detay ekranı
açılır: başvuru türü/alt türü, doktor, tanı listesi, etkin madde +
teşhis-reçete tablosu.

Ekran haritası (UIElementInspector capture'ları, kullanıcı EMRE 2026-07-05):
  Liste tablosu : form1:tableExKisiEndikasyonIzinList
    :N:text11 = Başvuru Numarası      :N:text13 = Başvuru Tarihi
    :N:text16 = Onay Tarihi           :N:text18 = Durumu (Onaylandı...)
    :N:text20 = Sağlık Tesisi         :N:text22 = Başvuru Nedeni
    :N:rowActionIzinDetaySorgu = satır tıklama → detay
  Detay ekranı  : form1:tableExIzinTaniList (tanılar),
                  form1:tableExEtkinMadde (etkin madde + teşhis-reçete)
  Geri          : form1:buttonGeriDon (detay→liste ve liste→reçete detay)

⚠️ KIRMIZI ÇİZGİ: SADECE OKUMA + navigasyon. f:t18'e yalnız sorgu TC'si
yazılır; hiçbir veri değiştirilmez.

Ön koşul: TAZE reçete detay ekranı (o sayfada daha önce başka TC
sorgulanmamış). Ana giriş: ``endikasyon_disi_izinleri_oku(tc)``.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from recete_kontrol.medula_rapor_tarayici import (
    _medula_hwnd_bul, _html_doc, _html_dom_hazir_bekle,
    _bildir, _bekle, ID_TC_INPUT, ID_BUTTON_GERI_DON,
)
from recete_kontrol.medula_ilac_gecmisi import (
    _elem_tikla, _tc_yaz, _val,
)

StatusCb = Optional[object]

# ─── Element ID'leri (capture teyitli — 2026-07-05) ─────────────────────────
ID_BUTTON_END_DISI = 'f:buttonKisiEndikasyonDisiSorgu'
END_TID = 'form1:tableExKisiEndikasyonIzinList'
_HUCRE = {
    'basvuru_no':     'text11',
    'basvuru_tarihi': 'text13',
    'onay_tarihi':    'text16',
    'durumu':         'text18',
    'saglik_tesisi':  'text20',
    'basvuru_nedeni': 'text22',
}


def _satirlari_oku(doc) -> List[Dict]:
    """Liste tablosundaki satırları oku (izinler az sayıda — tek sayfa
    varsayımı; 10 ardışık boş index'te durur)."""
    rows: List[Dict] = []
    miss = 0
    n = 0
    while n < 100 and miss < 10:
        bno = _val(doc, f'{END_TID}:{n}:{_HUCRE["basvuru_no"]}')
        if bno is None:
            miss += 1
            n += 1
            continue
        miss = 0
        kayit = {'idx': n, 'kaynak': 'medula'}
        for alan, sonek in _HUCRE.items():
            kayit[alan] = _val(doc, f'{END_TID}:{n}:{sonek}')
        kayit['basvuru_no'] = bno
        rows.append(kayit)
        n += 1
    return rows


def _detay_ac_ve_oku(hwnd: int, idx: int, cb: StatusCb = None) -> str:
    """Satıra tıkla → detay ekranı body metnini oku → Geri Dön → liste."""
    doc = _html_doc(hwnd)
    if doc is None:
        return ''
    if not _elem_tikla(doc, f'{END_TID}:{idx}:rowActionIzinDetaySorgu',
                       buton=True):
        _bildir(f'  UYARI: satır {idx} tıklanamadı', cb)
        return ''
    # Detay ekranı: tanı listesi tablosu gelene kadar bekle (20sn —
    # Medula yavaş anları, 2026-07-06)
    metin = ''
    for _ in range(40):
        _bekle(0.5)
        doc = _html_doc(hwnd)
        if doc is None:
            continue
        try:
            if doc.getElementById('form1:tableExIzinTaniList') is not None \
                    or doc.getElementById('form1:tableExEtkinMadde') is not None:
                body = doc.body
                metin = (body.innerText or '').strip() if body else ''
                break
        except Exception:
            pass
    # Geri Dön → liste
    try:
        doc = _html_doc(hwnd)
        _elem_tikla(doc, ID_BUTTON_GERI_DON, buton=True)
        for _ in range(20):
            _bekle(0.4)
            doc = _html_doc(hwnd)
            if doc is not None and _val(
                    doc, f'{END_TID}:{idx}:{_HUCRE["basvuru_no"]}') is not None:
                break
    except Exception:
        pass
    return metin[:8000]


def endikasyon_disi_izinleri_oku(
        tc: str,
        cb: StatusCb = None,
        detayli: bool = True,
        geri_don: bool = True) -> List[Dict]:
    """Reçete DETAY ekranı açıkken: TC yaz → End.Dışı (Yeni) → izinleri oku
    (detayli=True ise her iznin içine girip detay metnini topla) → Geri Dön.

    Returns: List[Dict] — her izin: basvuru_no, basvuru_tarihi, onay_tarihi,
    durumu, saglik_tesisi, basvuru_nedeni, detay_metni, kaynak='medula'.
    İzin yoksa/veri alınamazsa [].
    """
    if not tc or not (len(tc) == 11 and str(tc).isdigit()):
        _bildir(f'HATA: Geçersiz TC (End.Dışı)', cb)
        return []
    hwnd = _medula_hwnd_bul()
    if not hwnd:
        _bildir('HATA: Medula penceresi yok (End.Dışı)', cb)
        return []
    doc = _html_dom_hazir_bekle(hwnd, sure_sn=10.0, cb=cb) or _html_doc(hwnd)
    if doc is None:
        _bildir('HATA: HTML DOM proxy yok (End.Dışı)', cb)
        return []

    _bildir(f'End.Dışı: TC {tc[:3]}****{tc[-1]} yazılıyor', cb)
    if not _tc_yaz(doc, hwnd, tc, cb):
        return []

    _bildir('End.Dışı (Yeni) butonu', cb)
    if not _elem_tikla(doc, ID_BUTTON_END_DISI, buton=True):
        _bildir('HATA: End.Dışı butonu tıklanamadı', cb)
        return []

    # Liste yüklensin: row0 gelene kadar bekle (boş liste de olabilir —
    # timeout sonrası 0 satır normal)
    for _ in range(25):
        _bekle(0.4)
        doc = _html_doc(hwnd)
        if doc is not None and _val(
                doc, f'{END_TID}:0:{_HUCRE["basvuru_no"]}') is not None:
            break

    doc = _html_doc(hwnd)
    izinler = _satirlari_oku(doc) if doc is not None else []
    _bildir(f'End.Dışı: {len(izinler)} izin satırı bulundu', cb)

    if detayli:
        for izin in izinler:
            _bildir(f'  ▶ İzin detayı: {izin["basvuru_no"]} '
                    f'({izin["durumu"] or "?"})', cb)
            izin['detay_metni'] = _detay_ac_ve_oku(hwnd, izin['idx'], cb)
    else:
        for izin in izinler:
            izin['detay_metni'] = ''

    if geri_don:
        try:
            doc = _html_doc(hwnd)
            _elem_tikla(doc, ID_BUTTON_GERI_DON, buton=True)
            for _ in range(15):
                _bekle(0.4)
                doc = _html_doc(hwnd)
                try:
                    if doc is not None and doc.getElementById(
                            ID_TC_INPUT) is not None:
                        break
                except Exception:
                    pass
        except Exception:
            pass

    _bildir(f'End.Dışı: {len(izinler)} izin okundu', cb)
    return izinler
