# -*- coding: utf-8 -*-
"""Motor ↔ mevcut kontrol_xxx() drop-in uyumluluk katmanı.

GUI çağrı yerlerinde mevcut Python kontrol fonksiyonu yerine motor versiyonu
kullanılabilsin diye ince wrapper. Aynı `KontrolRaporu` dönüyor — ileri akış
(verdict_sartlar JSON serileştirmesi, Tab G şema renderı) hiçbir değişiklik
gerekmeden çalışır.

Kullanım:
    from recete_kontrol.sut_motor.uyumluluk import kontrol_fibrat_motor
    rapor = kontrol_fibrat_motor(ilac_sonuc)

GUI entegrasyonu: ortam değişkeni `ECZASIST_SUT_MOTOR` virgül ayraçlı
kategori listesi (örn. "FIBRAT") içeriyorsa o kategori motor ile değerlendirilir.
Boşsa mevcut Python fonksiyonu çalışır (varsayılan = motor kapalı).
"""
import os
from functools import lru_cache
from typing import Dict, List

from .motor import degerlendir, kural_yukle


_PROJE_KOK = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_KURAL_DOSYALARI: Dict[str, str] = {
    'FIBRAT': os.path.join(_PROJE_KOK, 'sut_kurallari', 'fibrat_4_2_28_b.json'),
    # Yeni kural eklemek = bu sözlüğe satır + JSON dosyası
}


@lru_cache(maxsize=16)
def _kural(kategori: str) -> Dict:
    """Kategori adına göre JSON kuralı yükle (cache'li)."""
    yol = _KURAL_DOSYALARI.get(kategori.upper())
    if not yol:
        raise KeyError(f"Bu kategori için motor kuralı tanımlı değil: {kategori}. "
                       f"Mevcut: {list(_KURAL_DOSYALARI)}")
    return kural_yukle(yol)


def kontrol_fibrat_motor(ilac_sonuc: Dict):
    """Motor ile Fibrat 4.2.28.B değerlendirmesi (kontrol_fibrat drop-in)."""
    return degerlendir(_kural('FIBRAT'), ilac_sonuc)


def motor_aktif_kategoriler() -> List[str]:
    """ECZASIST_SUT_MOTOR ortam değişkeninden aktif kategori listesi.

    Format: "FIBRAT" veya "FIBRAT,STATIN" gibi virgül ayraçlı.
    Boş/yoksa boş liste döner (motor hiçbir kategoride aktif değil).
    """
    val = (os.environ.get('ECZASIST_SUT_MOTOR') or '').strip()
    if not val:
        return []
    return [k.strip().upper() for k in val.split(',') if k.strip()]


def motor_aktif_mi(kategori: str) -> bool:
    """Verilen kategori için motor aktif mi? (env var bazlı)."""
    return kategori.upper() in motor_aktif_kategoriler()
