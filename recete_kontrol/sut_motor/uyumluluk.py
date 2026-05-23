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
import logging
import os
from functools import lru_cache
from typing import Dict, List

from .motor import degerlendir, kural_yukle

logger = logging.getLogger(__name__)


_PROJE_KOK = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_KURAL_DOSYALARI: Dict[str, str] = {
    'FIBRAT': os.path.join(_PROJE_KOK, 'sut_kurallari', 'fibrat_4_2_28_b.json'),
    'ARB_EK4F_M51': os.path.join(_PROJE_KOK, 'sut_kurallari', 'arb_ek4f_m51.json'),
    'MONO_ANTIHT': os.path.join(_PROJE_KOK, 'sut_kurallari',
                                'mono_antihipertansif_genel.json'),
    'KOMBI_ANTIHT_ARBDIS': os.path.join(_PROJE_KOK, 'sut_kurallari',
                                         'kombi_antihipertansif_arbdis.json'),
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


def kontrol_arb_ek4f_m51_motor(ilac_sonuc: Dict):
    """Motor ile EK-4/F m.51 ARB değerlendirmesi (kontrol_arb_ek4f_m51 drop-in).

    USTOR ile 4 yol (Y1-Y4) paralel değerlendirir:
      Y1: Mono ARB raporlu
      Y2: ARB+HCT raporlu (SGK 17.10.2016 istisnası)
      Y3: Kombi ARB diğer + monoterapi ibaresi
      Y4: Raporsuz + aile hekimi + ≤1 kutu

    DİĞER RAPOR BYPASS (post-process):
      Sonuç UYGUN_DEGIL ve sebebi Y3 (monoterapi ibaresi yok) ise hastanın
      geçmiş raporlarında ibare aranır; bulunursa sonuç DIGER_RAPOR_UYGUN'a
      yükseltilir.
    """
    rapor = degerlendir(_kural('ARB_EK4F_M51'), ilac_sonuc)
    return _arb_monoterapi_bypass_dene(rapor, ilac_sonuc)


def _arb_monoterapi_bypass_dene(rapor, ilac_sonuc: Dict):
    """Motor sonucu UYGUN_DEGIL ve sebebi monoterapi ibaresi ise bypass dene.

    Mevcut Python kontrol fonksiyonundaki bypass mantığının motor varyantı.
    Sadece Y3 başarısızlığında devreye girer (kombi ARB raporlu + ibare yok).
    """
    from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu
    if rapor.sonuc != KontrolSonucu.UYGUN_DEGIL:
        return rapor
    mesaj_l = (rapor.mesaj or '').lower()
    if 'monoterapi' not in mesaj_l and 'kombi' not in mesaj_l:
        return rapor

    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    if not hasta_tc:
        return rapor

    try:
        from recete_kontrol.diger_rapor_bypass import (
            gecmis_raporlarda_ibare_ara, IBARELER_ARB_MONOTERAPI)
        bypass = gecmis_raporlarda_ibare_ara(
            hasta_tc, list(IBARELER_ARB_MONOTERAPI),
            aktif_rapor_takip_no=(ilac_sonuc.get('rapor_takip_no') or '').strip(),
            kategori='HIPERTANSIYON')
    except Exception as e:
        logger.debug("ARB motor bypass sorgu hatası: %s", e)
        return rapor

    if not bypass:
        return rapor

    # Monoterapi atomu durumunu bypass'a yükselt
    for sart in (rapor.sartlar or []):
        if 'monoterapi' in (sart.ad or '').lower():
            sart.durum = SartDurumu.VAR
            sart.neden = f'Diğer rapor bypass: {bypass["ozet"]}'
            sart.bypass_kaynak = bypass["ozet"]
            break

    rapor.sonuc = KontrolSonucu.DIGER_RAPOR_UYGUN
    rapor.mesaj = (f'{rapor.mesaj} | BYPASS: hastanın diğer raporunda '
                    f'monoterapi ibaresi bulundu — {bypass["ozet"]}')
    rapor.bulunan_metin = bypass.get('snippet', '') or rapor.bulunan_metin
    if rapor.detaylar is None:
        rapor.detaylar = {}
    rapor.detaylar['bypass'] = bypass
    return rapor


def kontrol_mono_antihipertansif_motor(ilac_sonuc: Dict):
    """Motor ile mono antihipertansif (genel hüküm).

    on_kontrol: aynı reçetede ACE+ARB → UYGUN_DEGIL kontrendikasyon.
    Formül: doz aşımı yoksa UYGUN; mg parse edilemezse KE.
    """
    return degerlendir(_kural('MONO_ANTIHT'), ilac_sonuc)


def kontrol_kombi_antiht_arbdis_motor(ilac_sonuc: Dict):
    """Motor ile ARB-dışı kombi antihipertansif (genel hüküm).

    Kombi etken madde varlığı zaten 'monoterapi yetersizliği' örtük kanıtı.
    Her zaman UYGUN döner (kombi tespit edilemediyse YOK → ama dispatcher
    zaten kombiyi süzdüğü için pratikte VAR).
    """
    return degerlendir(_kural('KOMBI_ANTIHT_ARBDIS'), ilac_sonuc)


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
