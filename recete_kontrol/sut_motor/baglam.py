# -*- coding: utf-8 -*-
"""Baglam — Tek bir reçete satırı için motor erişim katmanı.

`ilac_sonuc` dict'ini sarıp atomların ihtiyacı olan normalize edilmiş
metinleri ve alanları bir kez hesaplar; her atom çağrısında yeniden
parse etmemek için cache'ler.
"""
from typing import Dict, List, Optional


class Baglam:
    """Bir reçete kalemi için motor değerlendirme bağlamı.

    Atomlar `baglam.metin_lower`, `baglam.teshis_metin`, `baglam.doktor_uzm`
    gibi alanları okur. `_tr_lower` ve `_tum_metinleri_birlesir` helperları
    `recete_kontrol.sut_kontrolleri` modülünden ödünç alınır (tek kaynak).
    """

    def __init__(self, ilac_sonuc: Dict):
        # Geç import — döngüsel bağımlılığı önle (sut_kontrolleri büyük modül)
        from recete_kontrol import sut_kontrolleri as _sk

        self.ham: Dict = ilac_sonuc or {}
        self.ilac_adi: str = (self.ham.get('ilac_adi') or '').upper()
        self.rapor_kodu: str = (self.ham.get('rapor_kodu') or '').strip()
        self.doktor_uzm: str = (self.ham.get('doktor_uzmanligi') or '').strip()
        self.recete_teshisleri: List[str] = self.ham.get('recete_teshisleri', []) or []
        self.teshis_metin: str = (' '.join(self.recete_teshisleri).upper()
                                  if self.recete_teshisleri else '')

        self.tum_metin: str = _sk._tum_metinleri_birlesir(self.ham) or ''
        self.birlesik_metin: str = (self.tum_metin + ' ' + self.teshis_metin).strip()
        self.metin_lower: str = (_sk._tr_lower(self.birlesik_metin)
                                 if self.birlesik_metin else '')

        # Geçmiş rapor verileri (FERİDE EGE 3KTNEKA — 2026-05-16):
        # GUI önceki raporları toplar; statin/fibrat kalıbı: KV risk faktörleri
        # aktif raporda olmasa bile geçmiş raporlardan tespit edilebilir.
        self.diger_icd: List[str] = self.ham.get('diger_raporlar_icd') or []
        self.diger_rapor_metinleri: List[str] = (
            self.ham.get('diger_rapor_metinleri') or [])

        # Helper kısayolları (atomlar bu kanaldan kullanır)
        self._sk = _sk

    def metin_bos_mu(self) -> bool:
        return not self.metin_lower.strip()

    def rapor_kodu_yok_mu(self) -> bool:
        return not self.rapor_kodu

    def __repr__(self) -> str:
        return (f"Baglam(ilac={self.ilac_adi!r}, rk={self.rapor_kodu!r}, "
                f"uzm={self.doktor_uzm!r}, teshis={self.teshis_metin!r}, "
                f"metin_uzunluk={len(self.metin_lower)})")
