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
    """Motor sonucu UYGUN_DEGIL veya ŞÜPHELİ ve sebebi Y3'ün monoterapi atomu
    ise bypass dene (paralel-OR semantiği).

    Atomik şemada Y3'ün monoterapi atomu:
       monoterapi_yetersiz := aktif_rapor_ibaresi  ∨  diger_raporda_ibare
    Aktif raporda ibare yoksa (VEYA aktif metin sessizse) hastanın diğer
    reçetelerine ilintili raporlarda bakılır; bulunursa monoterapi atomu VAR
    sayılır ve Y3'ün diğer atomları zaten VAR ise sonuç DIGER_RAPOR_UYGUN.

    Önceki bug (2026-05-23 TAMAM KARTAL / FAZİLE KULAN pilot):
      1. Trigger sadece UYGUN_DEGIL idi — Y3 monoterapi atomu KE olunca motor
         ŞÜPHELİ üretiyor, bypass hiç denenmiyordu.
      2. Sadece yerel cache (gecmis_raporlarda_ibare_ara) sorgulanıyordu —
         Botanik EOS'taki RaporAnaAciklamalar atlanmıştı. Kullanıcı kuralı
         (project_diger_rapor_uygun_bypass.md, 2026-05-23): EOS asıl kaynak,
         cache fallback.
    """
    from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu
    # 1) Trigger genişletildi: UYGUN_DEGIL VEYA ŞÜPHELİ
    if rapor.sonuc not in (KontrolSonucu.UYGUN_DEGIL,
                           KontrolSonucu.KONTROL_EDILEMEDI):
        return rapor

    # 2) Sartlar listesinde monoterapi atomunu bul. VAR ise zaten Y3 geçmiş,
    #    bypass anlam taşımaz (başka bir atom başarısız demektir).
    mono_sart = None
    for s in (rapor.sartlar or []):
        if 'monoterapi' in (s.ad or '').lower():
            mono_sart = s
            break
    if mono_sart is None or mono_sart.durum == SartDurumu.VAR:
        return rapor

    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    if not hasta_tc:
        return rapor

    # Aktif rapor metni — kendi metinde arayıp bulmasın diye hariç tut
    rap_acklari = ilac_sonuc.get('rapor_aciklamalari') or []
    aktif_rap_ack = (' '.join(str(x) for x in rap_acklari)
                     if rap_acklari else '')

    try:
        from recete_kontrol.diger_rapor_bypass import (
            eos_raporlarda_ibare_ara, gecmis_raporlarda_ibare_ara,
            IBARELER_ARB_MONOTERAPI)
        # 3) ÖNCELİK: Botanik EOS — RaporAna.RaporAnaAciklamalar
        bypass = eos_raporlarda_ibare_ara(
            hasta_tc, list(IBARELER_ARB_MONOTERAPI),
            aktif_rapor_aciklama=aktif_rap_ack)
        # 4) FALLBACK: yerel MEDULA cache (hasta_rapor_gecmisi.db)
        if bypass is None:
            bypass = gecmis_raporlarda_ibare_ara(
                hasta_tc, list(IBARELER_ARB_MONOTERAPI),
                aktif_rapor_takip_no=(ilac_sonuc.get('rapor_takip_no')
                                       or '').strip(),
                kategori='HIPERTANSIYON')
    except Exception as e:
        logger.debug("ARB motor bypass sorgu hatası: %s", e)
        return rapor

    if not bypass:
        return rapor

    # 5) Monoterapi atomunu bypass ile VAR'a yükselt
    mono_sart.durum = SartDurumu.VAR
    mono_sart.neden = f'Diğer rapor bypass: {bypass["ozet"]}'
    mono_sart.bypass_kaynak = bypass["ozet"]

    # 6) Y3 yolu bypass sonrası tam mı? Mono atomunun grubundaki diğer
    #    atomların hepsinin VAR olması gerek. Aksi halde Y3 hala başarısız —
    #    sonucu değiştirmiyoruz, atom durumu yine de güncellendi (görsel
    #    şema panelinde bypass_kaynak görünür).
    y3_grup = mono_sart.grup or ''
    if y3_grup:
        y3_atomlar = [s for s in (rapor.sartlar or [])
                      if (s.grup or '') == y3_grup]
        y3_tam = all(s.durum == SartDurumu.VAR for s in y3_atomlar)
    else:
        y3_tam = True  # Grup yoksa tek mono atomu — bypass yeterli

    if not y3_tam:
        # Y3'ün başka atomları da kırık — bypass sonucu değiştiremez
        logger.debug("ARB bypass: monoterapi VAR'a yükseldi ama Y3 hala "
                     "tam değil — sonuç değişmedi")
        return rapor

    rapor.sonuc = KontrolSonucu.DIGER_RAPOR_UYGUN
    rapor.mesaj = (f'{rapor.mesaj} | BYPASS: aktif raporda monoterapi '
                   f'ibaresi yok; hastanın diğer raporunda bulundu — '
                   f'{bypass["ozet"]}')
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
