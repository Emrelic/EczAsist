"""
Kontrolü gereksiz ilaçlar listesi — aylık reçete kontrol ekranı filtresi.

Eczacının "bu ilaç hiç SUT kontrolü gerektirmiyor" dediği ilaçları kalıcı
olarak saklar. Aylık reçete kontrol ekranındaki
"🚫 Kontrolü gereksiz ilaçları gizle" kutusu işaretliyken bu listedeki
ilaçlara ait satırlar tablodan gizlenir.

Eşleşme kuralları (her biri normalize edilir: TR-upper + boşluk sadeleştirme):
  - ilac_adlari  : İlaç adı (UrunAdi)        → TAM eşleşme
  - atc_kodlari  : ATC kodu                  → ÖNEK (prefix) eşleşme
                   (ör. "A11" → tüm A11* vitaminler gizlenir)
  - etken_adlari : Etken madde (ATCTurkce)   → TAM eşleşme

GÜVENLİK: Yalnızca yerel JSON dosyası kullanılır. Botanik EOS'a (SQL Server)
hiçbir erişim yoktur — KIRMIZI ÇİZGİ §2 kapsamı dışıdır.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOSYA_YOLU = os.path.join(_SCRIPT_DIR, "kontrol_disi_ilaclar.json")

_ANAHTARLAR = ("ilac_adlari", "atc_kodlari", "etken_adlari")


def normalize(x) -> str:
    """Eşleşme için tek tip metin: TR-upper + iç boşlukları sadeleştir.

    Hem saklanan hem sorgulanan değer aynı fonksiyondan geçtiği için
    büyük/küçük harf ve fazla boşluk farkları eşleşmeyi bozmaz.
    """
    return " ".join((x or "").strip().upper().split())


def bos_yapi() -> dict:
    return {k: [] for k in _ANAHTARLAR}


def yukle() -> dict:
    """JSON'dan listeyi yükle. Dosya yok/bozuksa boş yapı döner."""
    if not os.path.exists(DOSYA_YOLU):
        return bos_yapi()
    try:
        with open(DOSYA_YOLU, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: list(data.get(k, []) or []) for k in _ANAHTARLAR}
    except Exception as e:
        logger.warning("kontrol_disi_ilaclar.json okunamadi: %s", e)
        return bos_yapi()


def kaydet(data: dict) -> bool:
    """Listeyi normalize edip (tekilleştirip sıralayarak) JSON'a yaz."""
    try:
        temiz = {
            k: sorted({normalize(x) for x in data.get(k, []) if normalize(x)})
            for k in _ANAHTARLAR
        }
        with open(DOSYA_YOLU, "w", encoding="utf-8") as f:
            json.dump(temiz, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("kontrol_disi_ilaclar.json yazilamadi: %s", e)
        return False


def setler(data: dict = None):
    """Hızlı eşleşme için normalize edilmiş 3 set döner:
    (ilac_set, atc_set, etken_set). data verilmezse dosyadan yükler."""
    if data is None:
        data = yukle()
    return (
        {normalize(x) for x in data.get("ilac_adlari", [])},
        {normalize(x) for x in data.get("atc_kodlari", [])},
        {normalize(x) for x in data.get("etken_adlari", [])},
    )


def eslesir_mi(ilac_adi, atc, etken, setler_tuple=None) -> bool:
    """Bir satır (ilaç) kontrolü gereksiz listesinde mi?

    setler_tuple verilirse (ilac_set, atc_set, etken_set) tekrar tekrar
    dosya okumadan hızlı eşleşme yapılır — tablo render döngüsü için.
    """
    if setler_tuple is None:
        ilac_set, atc_set, etken_set = setler()
    else:
        ilac_set, atc_set, etken_set = setler_tuple
    if not (ilac_set or atc_set or etken_set):
        return False

    n_ilac = normalize(ilac_adi)
    if n_ilac and n_ilac in ilac_set:
        return True

    n_etken = normalize(etken)
    if n_etken and n_etken in etken_set:
        return True

    n_atc = normalize(atc)
    if n_atc:
        for onek in atc_set:
            if onek and n_atc.startswith(onek):
                return True

    return False
