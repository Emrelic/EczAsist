# -*- coding: utf-8 -*-
"""SUT metni kayıt — kategori → resmi SUT madde lafzı eşlemesi.

Atomik şema panelinin sağ tarafında "📖 SUT Kuralı" olarak gösterilir
(Medula ilaç bilgisi mesajı ile karıştırılmamalı: o ekrandaki
'medula_msj' alanı Medula provizyon yanıtıdır; bu modül SGK SUT
mevzuat lafzını verir).

Kaynak öncelik sırası:
  1. `sut_kurallari/<kategori>.json` dosyasında `sut_metni` alanı
     (motor üzerinden değerlendirilen kategoriler — tek kaynak)
  2. Bu modülde inline `_FALLBACK_METINLER` sözlüğü
     (henüz motora göçmemiş kategoriler için geçici)

Yeni kategori ekleme:
  - Motor üzerinden değerlendiriliyorsa → JSON kuralında `sut_metni` alanı
  - Henüz motor yoksa → `_FALLBACK_METINLER` içine kategori → metin ekle

Kaynak: docs/sut/SUT_tam_metin.txt (mevzuat.gov.tr MevzuatNo=17229).
"""
import json
import os
from functools import lru_cache
from typing import Dict, Optional


# Motor JSON kural dosyaları (uyumluluk.py'dekiyle aynı yapı)
_PROJE_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_MOTOR_KURAL_DOSYALARI: Dict[str, str] = {
    'FIBRAT': os.path.join(_PROJE_KOK, 'sut_kurallari', 'fibrat_4_2_28_b.json'),
}


# Henüz motora geçmemiş kategoriler için inline fallback.
# Yeni kategori burada veya tercihen motor JSON'da tanımlanmalı.
# Kaynak: docs/sut/SUT_tam_metin.txt (mevzuat.gov.tr SUT).
_FALLBACK_METINLER: Dict[str, str] = {
    # SUT 4.2.28.A — Statinler (özet — tam metin için docs/sut)
    # Eklenmesi planlanan; şimdilik boş, GUI fallback davranışı devreye girer.
}


@lru_cache(maxsize=32)
def _motor_kuralindan_metin(kategori: str) -> Optional[str]:
    """Motor JSON kuralı varsa içinden `sut_metni` alanını oku."""
    yol = _MOTOR_KURAL_DOSYALARI.get(kategori.upper())
    if not yol or not os.path.exists(yol):
        return None
    try:
        with open(yol, 'r', encoding='utf-8') as f:
            kural = json.load(f)
        metin = kural.get('sut_metni')
        if metin:
            return str(metin).strip()
    except (OSError, json.JSONDecodeError):
        return None
    return None


def sut_metni_getir(kategori: Optional[str]) -> Optional[str]:
    """Kategori adı (FIBRAT/STATIN/YOAK/...) → resmî SUT madde lafzı.

    Args:
        kategori: 'verdict_kategori' alanı (örn. "FIBRAT", "STATIN").
                  Boş/None ise None döner.

    Returns:
        SUT lafzı (str). Bulunamazsa None.
    """
    if not kategori:
        return None
    k = kategori.upper().strip()
    metin = _motor_kuralindan_metin(k)
    if metin:
        return metin
    metin = _FALLBACK_METINLER.get(k)
    if metin:
        return metin.strip()
    return None


def sut_metni_var_mi(kategori: Optional[str]) -> bool:
    """Bu kategori için kayıtlı SUT lafzı var mı?"""
    return sut_metni_getir(kategori) is not None
