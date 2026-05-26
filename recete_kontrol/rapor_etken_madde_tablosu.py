"""Hastanın TÜM raporlu etken maddeleri × tarih tablosu.

Kullanıcı kararı 2026-05-25:
  📊 Raporlu Etken Maddeler Tablosu — hastanın hangi etken maddenin hangi
  tarihli raporda çıkarıldığını gösterir. Etken bazında ilk tarih =
  başlangıç raporu.

Veri kaynağı:
  - yerel `hasta_rapor_gecmisi.db` (Medula taraması sonrası)
  - her satırdaki `detay_metni`'nden "Rapor Etkin Madde Bilgileri" parse

Satır şeması (kullanıcı isteği):
    etken_madde   — TENOFOVIR DISOPROKSIL FUMARAT
    form          — Ağızdan katı
    doz           — Günde 1 x 1.0 Adet
    tarih         — 26/01/2022 (rapor başlangıç tarihi)
    rapor_kodu    — 14.01
    tani          — Hepatit B Enfeksiyon
    icd_kodu      — B18.1
    rapor_no      — 2660355905 (RaporNo, takip değil)
    rapor_takip_no — 372052898
    aciklama      — Rapor açıklama metni (ilk 200 char)
    eklenme_zamani — 26/01/2022 16:21 (Medula içeri kayıt zamanı)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from recete_kontrol.hasta_rapor_gecmisi_db import (
    hasta_raporlarini_oku, sema_olustur)


logger = logging.getLogger(__name__)


@dataclass
class EtkenTabloSatiri:
    etken_madde: str = ''
    form: str = ''
    doz: str = ''
    tarih: str = ''                 # rapor başlangıç tarihi (DD/MM/YYYY)
    rapor_kodu: str = ''
    tani: str = ''
    icd_kodu: str = ''
    rapor_no: str = ''              # RaporNo (RaporTakipNo'dan farklı)
    rapor_takip_no: str = ''
    aciklama: str = ''
    eklenme_zamani: str = ''        # Medula'nın raporu kaydettiği zaman
    is_baslangic: bool = False      # bu etken için en eski tarih mi?


# ═════════════════════════════════════════════════════════════════════════
# Parser — "Rapor Etkin Madde Bilgileri" bölümünden ilaç satırlarını çıkar
# ═════════════════════════════════════════════════════════════════════════

# Medula form kelimeleri (etken sonrası ayırıcı)
_FORM_KELIMELER = (
    'Ağızdan', 'Agizdan',
    'Damar', 'Damariçi', 'Damariçine',
    'Deri', 'Deriüstü', 'Deri üstü',
    'Soluma', 'İnhalasyon',
    'Diş', 'Göz', 'Burun', 'Kulak',
    'Vücut', 'Kas',
    'Rektal', 'Vajinal',
    'Topikal', 'Subkutan',
)

# "Rapor Etkin Madde Bilgileri" bölüm başlangıcı + sonu
_RE_BOLUM = re.compile(
    r'Rapor Etkin Madde Bilgileri\s*(.*?)'
    r'(?:Son\s+[SŞ]ifre|UYGMEDECZ|Doktor Bilgileri|Tan[ıi] Bilgileri|\Z)',
    re.DOTALL | re.IGNORECASE)

# Form ayırma — etken_madde'nin neresi biter, form nerede başlar
_FORM_PAT = re.compile(
    r'(' + '|'.join(_FORM_KELIMELER) + r')',
    re.IGNORECASE)

# Doz pattern — "Günde 1 x 1.0 Adet" / "Haftada 2 x 0.5 Ml" vb.
_DOZ_PAT = re.compile(
    r'(G[üu]nde|Haftada|Ayda|Saatte)\s+\d+\s*x\s*[\d.,]+\s*\w+',
    re.IGNORECASE)

# Tarih+saat sonu — "26/01/2022 16:21" / "26.01.2022 16:21"
_TARIH_SAAT_PAT = re.compile(
    r'(\d{1,2}[./]\d{1,2}[./]\d{4}(?:\s+\d{1,2}:\d{2})?)')

# Kod prefix — "SGKFRZ" / "SGKFRY" 6 hane sabit (SGK + 3 hane).
# Bug 2026-05-25: greedy / lazy ile boundary bulunamıyordu — Medula veri
# örneklerinde tüm kodlar 6 hane (SGK + 3 hane). Diğer uzunluklar görülürse
# bu sabit uzaltılır.
_KOD_PAT = re.compile(r'^(SGK[A-Z]{3})')


def _parse_etkin_madde_bolumu(detay_metni: str) -> List[dict]:
    """Detay metninden 'Rapor Etkin Madde Bilgileri' parse → list[dict].

    Her satır şu alanları içerir: kod, etken, form, doz, eklenme_zamani.
    Satır birleşik olduğu için form/doz/tarih anchor'larına göre kesilir.
    """
    if not detay_metni:
        return []
    m = _RE_BOLUM.search(detay_metni)
    if not m:
        return []
    bolum = m.group(1).strip()
    if not bolum:
        return []

    sonuc: List[dict] = []
    # Satırlara böl — \r\n veya \n
    for raw in re.split(r'[\r\n]+', bolum):
        raw = raw.strip()
        if not raw or 'Kodu' in raw[:20]:  # başlık satırı
            continue

        # Kod prefix yakala
        kod_m = _KOD_PAT.match(raw)
        if not kod_m:
            continue
        kod = kod_m.group(1)
        rest = raw[len(kod):]

        # Form anchor — etken/form arasını kes
        form_m = _FORM_PAT.search(rest)
        if not form_m:
            continue
        etken = rest[:form_m.start()].strip()
        post_form = rest[form_m.start():]

        # Doz anchor
        doz_m = _DOZ_PAT.search(post_form)
        if doz_m:
            form = post_form[:doz_m.start()].strip()
            post_doz = post_form[doz_m.start():]
            # Doz sonu — tarih veya sonu
            tarih_m = _TARIH_SAAT_PAT.search(post_doz)
            if tarih_m:
                doz = post_doz[:tarih_m.start()].strip()
                eklenme = tarih_m.group(1)
            else:
                doz = post_doz.strip()
                eklenme = ''
        else:
            # Doz bulunamadıysa form sonu / tarih
            tarih_m = _TARIH_SAAT_PAT.search(post_form)
            if tarih_m:
                form = post_form[:tarih_m.start()].strip()
                doz = ''
                eklenme = tarih_m.group(1)
            else:
                form = post_form.strip()
                doz = ''
                eklenme = ''

        sonuc.append({
            'kod': kod,
            'etken_madde': etken,
            'form': form,
            'doz': doz,
            'eklenme_zamani': eklenme,
        })
    return sonuc


# ═════════════════════════════════════════════════════════════════════════
# Public API — tablo üretici
# ═════════════════════════════════════════════════════════════════════════

def hasta_etken_tablo(hasta_tc: str) -> List[EtkenTabloSatiri]:
    """Hastanın tüm raporlarındaki etken maddeleri × tarih tablosu.

    Args:
        hasta_tc: 11 haneli hasta TC

    Returns:
        list[EtkenTabloSatiri] — tarih sıralı (en yeni → en eski).
        Her etken_madde için en eski tarihli satırda is_baslangic=True.
        Boş liste = hasta yerel DB'de yok ya da hiç rapor yok.
    """
    if not hasta_tc:
        return []
    try:
        sema_olustur()
        raporlar = hasta_raporlarini_oku(hasta_tc)
    except Exception as e:
        logger.error('hasta_etken_tablo DB hatası: %s', e)
        return []

    satirlar: List[EtkenTabloSatiri] = []
    for rapor in raporlar:
        ilaclar = _parse_etkin_madde_bolumu(rapor.detay_metni or '')
        if not ilaclar:
            # Detay parse edilemediyse en azından metadata'lı bir satır göster
            satirlar.append(EtkenTabloSatiri(
                etken_madde='(parse edilemedi)',
                tarih=rapor.baslangic_tarihi or '',
                rapor_kodu=rapor.rapor_kodu or '',
                tani=rapor.tani or '',
                icd_kodu=rapor.icd_kodu or '',
                rapor_takip_no=rapor.rapor_takip_no or '',
                aciklama=(rapor.detay_metni or '')[:200].strip(),
            ))
            continue

        # Aciklama — detay_metni'nden "Açıklamalar" bölümü (ilk 200 char)
        aciklama = _aciklama_cikar(rapor.detay_metni or '')[:200]
        # RaporNo — detay metnindeki "Rapor Numarası (*): ..." kalıbı
        rapor_no = _rapor_no_cikar(rapor.detay_metni or '')

        for ilac in ilaclar:
            satirlar.append(EtkenTabloSatiri(
                etken_madde=ilac['etken_madde'],
                form=ilac['form'],
                doz=ilac['doz'],
                tarih=rapor.baslangic_tarihi or '',
                rapor_kodu=rapor.rapor_kodu or '',
                tani=rapor.tani or '',
                icd_kodu=rapor.icd_kodu or '',
                rapor_no=rapor_no,
                rapor_takip_no=rapor.rapor_takip_no or '',
                aciklama=aciklama,
                eklenme_zamani=ilac['eklenme_zamani'],
            ))

    # Etken bazında EN ESKİ tarihi tespit et + is_baslangic flag set et
    en_eski_per_etken: dict = {}
    for s in satirlar:
        et = s.etken_madde.upper()
        if not et or et == '(PARSE EDILEMEDI)':
            continue
        # Tarih DD/MM/YYYY → sort key (YYYYMMDD)
        key = _tarih_sort_key(s.tarih)
        if et not in en_eski_per_etken or key < en_eski_per_etken[et][0]:
            en_eski_per_etken[et] = (key, id(s))
    for s in satirlar:
        et = s.etken_madde.upper()
        if et in en_eski_per_etken and en_eski_per_etken[et][1] == id(s):
            s.is_baslangic = True

    # Sırala — en yeni en üstte, etken bazında grupla (ikincil sıralama)
    satirlar.sort(key=lambda s: (s.etken_madde.upper(),
                                   -int(_tarih_sort_key(s.tarih) or '0')))
    return satirlar


def _aciklama_cikar(metin: str) -> str:
    """Detay metninden 'Açıklamalar' bölümünden ilk anlamlı paragraf."""
    if not metin:
        return ''
    m = re.search(
        r'A[çc]?[ıi]klamalar(?:Eklenme Zaman[ıi])?\s*(.*?)'
        r'(?:Tan[ıi] Bilgileri|Doktor Bilgileri|Rapor Etkin|\Z)',
        metin, re.DOTALL | re.IGNORECASE)
    if not m:
        return ''
    txt = m.group(1).strip()
    # İlk \n\n veya 200 char
    para = re.split(r'\r?\n\r?\n', txt, maxsplit=1)[0]
    return para.strip()


def _rapor_no_cikar(metin: str) -> str:
    """Detay metninden 'Rapor Numarası (*): NNNN' parse et."""
    if not metin:
        return ''
    m = re.search(
        r'Rapor\s+Numaras[ıi]\s*\([*]?\)?\s*:\s*(\d+)', metin)
    return m.group(1) if m else ''


def _tarih_sort_key(tarih_str: str) -> str:
    """DD/MM/YYYY → YYYYMMDD (sort key)."""
    if not tarih_str:
        return '00000000'
    m = re.match(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', tarih_str.strip())
    if not m:
        return '00000000'
    return f'{m.group(3)}{m.group(2).zfill(2)}{m.group(1).zfill(2)}'


__all__ = [
    'EtkenTabloSatiri',
    'hasta_etken_tablo',
]
