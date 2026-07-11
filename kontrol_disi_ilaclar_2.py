"""
Kontrolü gereksiz 2. KADEME ilaçlar — kullanıcının 1. kademeden ayrı tuttuğu
ikinci "kontrol gerektirmez" listesi.

Davranış 1. kademe (kontrol_disi_ilaclar.py) ile birebir aynıdır: listedeki
ilaç, gizleme kutusu işaretliyken tablodan gizlenir / SQL'de getirme
işaretliyken sorguya hiç gelmez. Raporlu-mesajlı gibi ek koşul YOKTUR —
hangi ilacın 2. kademe olduğu tamamen kullanıcının kararıdır (2026-07-07).
Tek fark: ayrı JSON dosyası, ayrı checkbox'lar.

Eşleşme kuralları 1. kademe ile birebir aynı (ad TAM / ATC ÖNEK / etken TAM);
tüm fonksiyonlar kontrol_disi_ilaclar.py'dan dosya parametresiyle delege edilir.

GÜVENLİK: Yalnızca yerel JSON dosyası kullanılır — Botanik EOS'a erişim yok.
"""

import os

import kontrol_disi_ilaclar as _k1

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOSYA_YOLU = os.path.join(_SCRIPT_DIR, "kontrol_disi_ilaclar_2.json")

# Saf yardımcılar — dosyadan bağımsız, doğrudan paylaşılır
normalize = _k1.normalize
bos_yapi = _k1.bos_yapi
eslesir_mi = _k1.eslesir_mi


def yukle() -> dict:
    return _k1.yukle(DOSYA_YOLU)


def kaydet(data: dict) -> bool:
    return _k1.kaydet(data, DOSYA_YOLU)


def setler(data: dict = None):
    return _k1.setler(data, DOSYA_YOLU)


def sql_eslesme_kosulu(data: dict = None,
                       urun_adi_kolon: str = "u.UrunAdi",
                       atc_kod_kolon: str = "atc.ATCKodu",
                       etken_kolon: str = "atc.ATCTurkce") -> str:
    return _k1.sql_eslesme_kosulu(data, urun_adi_kolon, atc_kod_kolon,
                                   etken_kolon, dosya=DOSYA_YOLU)
