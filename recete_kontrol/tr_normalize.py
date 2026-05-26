# -*- coding: utf-8 -*-
"""Türkçe ↔ ASCII karakter normalize — tüm SUT kontrol modüllerinin tek otoritesi.

Sorun: Python `.upper()` ve `.lower()` Türkçe karakter dönüşümünü tam yapmaz:
- `'İ'.upper()` → `'İ'` (büyük kalır, ASCII 'I' ile eşleşmez)
- `'I'.lower()` → `'i'` (Türkçe 'ı' yerine 'i' verir)
- `'İ'.lower()` → `'i̇'` (combining dot above ekler — regex'i bozar)
- `'PİOGLİTAZON'.upper()` → `'PİOGLİTAZON'` (set elemanı 'PIOGLITAZON' ile NE eşit NE in)

Bu modül iki ana fonksiyon sağlar:
- `norm_tr_upper(s)` — TR→ASCII upper (ilaç adı / etken madde / küme eşleme için)
- `norm_tr_lower(s)` — TR→ASCII lower (rapor metni / regex search için)

Tüm parser/eşleştirme kodu bunları kullanmalı. Doğrudan `.upper()`/`.lower()`
kullanılırsa Türkçe karakter tuzağı tekrar görülür.

Bkz. memory `feedback_tr_lower_parser_tuzagi.md`.
"""
from __future__ import annotations

# Eşleştirme:
#   ı/i/I/İ → I/i (büyük/küçük varyantına göre)
#   o/ö/O/Ö → O/o
#   u/ü/U/Ü → U/u
#   ç/Ç → C/c
#   ş/Ş → S/s
#   ğ/Ğ → G/g
_UPPER_MAP = str.maketrans({
    'İ': 'I', 'I': 'I', 'ı': 'I', 'i': 'I',
    'Ö': 'O', 'ö': 'O', 'O': 'O', 'o': 'O',
    'Ü': 'U', 'ü': 'U', 'U': 'U', 'u': 'U',
    'Ç': 'C', 'ç': 'C', 'C': 'C', 'c': 'C',
    'Ş': 'S', 'ş': 'S', 'S': 'S', 's': 'S',
    'Ğ': 'G', 'ğ': 'G', 'G': 'G', 'g': 'G',
    # Lowercase'in tüm harflerini direkt upper'a çevirmek için
    # str.upper() önce uygulanıp sonra translate de yapılabilir — biz
    # her iki yolu da destekleyelim diye .upper() + translate iki-aşamalı kullanıyoruz.
})

_LOWER_MAP = str.maketrans({
    'İ': 'i', 'I': 'i', 'ı': 'i', 'i': 'i',
    'Ö': 'o', 'ö': 'o', 'O': 'o', 'o': 'o',
    'Ü': 'u', 'ü': 'u', 'U': 'u', 'u': 'u',
    'Ç': 'c', 'ç': 'c', 'C': 'c', 'c': 'c',
    'Ş': 's', 'ş': 's', 'S': 's', 's': 's',
    'Ğ': 'g', 'ğ': 'g', 'G': 'g', 'g': 'g',
    '̇': '',  # combining dot above (İ.lower() sonrası gelir)
})


def norm_tr_upper(metin: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirip UPPER döndürür.

    Kullanım: ilaç adı / etken madde / ICD kodu / küme arama (`set` üyeleri ASCII).
    Tüm set/küme tanımları ASCII (büyük) olmalıdır.

    Örnek:
        norm_tr_upper('PİOGLİTAZON')  # 'PIOGLITAZON'
        norm_tr_upper('İnsülin Glarjin')  # 'INSULIN GLARJIN'
    """
    if not metin:
        return ''
    # Önce upper() — küçük harfleri büyüğe çevir, sonra translate ile TR→ASCII
    return metin.upper().translate(_UPPER_MAP)


def norm_tr_lower(metin: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirip LOWER döndürür + combining-dot temizler.

    Kullanım: rapor metni / regex search (`re.search(...)` öncesi).
    Pattern'lar da ASCII olmalıdır.

    Örnek:
        norm_tr_lower('DİĞER BASAL İNSÜLİN')  # 'diger basal insulin'
        norm_tr_lower('Türk')  # 'turk'
    """
    if not metin:
        return ''
    # Önce lower() — büyük harfleri küçüğe çevir, sonra translate ile TR→ASCII + combining-dot temizle
    return metin.lower().translate(_LOWER_MAP)


def iceriyor_normalize(metin: str, kume) -> bool:
    """`metin` içinde `kume` üyelerinden herhangi biri (normalize edilerek) geçiyor mu?

    Hem metni hem küme üyelerini norm_tr_upper'dan geçirir — küme üyeleri ASCII bile olsa
    metin TR karakterli olabilir. Performans için küme önceden ASCII tutulmalı.
    """
    metin_n = norm_tr_upper(metin)
    return any(norm_tr_upper(k) in metin_n for k in kume)
