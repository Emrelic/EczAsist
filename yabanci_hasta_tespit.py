# -*- coding: utf-8 -*-
"""Yabancı uyruklu hasta tespiti — TC kimlik öneki + geçici koruma kapsamı.

Türkiye Cumhuriyeti vatandaşı OLMAYAN kişilere verilen kimlik numaraları
'99' (Yabancı Kimlik Numarası / YKN) veya '98' (eski geçici koruma "şahıs
numarası") ile başlar. Türk vatandaşlarının TCKN'leri bu aralıklarda olmaz;
'98'/'99' dışında vatandaş-olmayan için kullanılan başka bir önek yoktur
(araştırma kaynağı: teyit.org + NVİ kimlik numarası yapısı, 2026-06).

İş kuralı (Topkapı SGK kağıdı):
    98/99 ile başlayan (yabancı uyruklu) bir hastanın reçetesi GEÇİCİ KORUMA
    kapsamında DEĞİLSE, bu kişi "yabancı SGK'lı" sayılır ve reçetesi için
    Topkapı SGK'dan kağıt getirmesi gerekir. Geçici koruma / mülteci /
    sığınmacı kapsamındakiler bu uyarının DIŞINDADIR.

⚠️ KALİBRASYON: Geçici korumanın Botanik EOS `Kapsam` tablosunda nasıl
etiketlendiği eczaneden eczaneye değişebilir (bazı sürümlerde ayrı bir kapsam
adı hiç bulunmayabilir). `GECICI_KORUMA_ANAHTARLARI` listesi, "Yabancı Uyruklu
Hasta Tespit Raporu"ndaki gerçek kapsam adlarına bakılarak gözden geçirilmeli.
Anahtar bulunamazsa istisna uygulanmaz (güvenli taraf: 98/99 → uyarı verir).
"""

# Vatandaş-olmayan TC/YKN önekleri (Türk vatandaşı TCKN'leri bu aralıkta olmaz)
YABANCI_TC_ONEKLERI = ("98", "99")

# Geçici koruma / uluslararası koruma kapsamı işaretleri (uyarıdan muaf).
# Türkçe karakterler `_normalize` ile sadeleştirildiği için anahtarlar da sade.
GECICI_KORUMA_ANAHTARLARI = (
    "GECICI KORUMA",
    "GECICI KORUNMA",
    "MULTECI",
    "SIGINMACI",
)


def _normalize(s) -> str:
    """Büyük harfe çevir + Türkçe karakterleri ASCII'ye indir (eşleştirme için)."""
    if not s:
        return ""
    s = str(s).upper()
    for a, b in (("İ", "I"), ("Ş", "S"), ("Ç", "C"),
                 ("Ğ", "G"), ("Ü", "U"), ("Ö", "O")):
        s = s.replace(a, b)
    return s


def tc_yabanci_mi(tc) -> bool:
    """TC '98' veya '99' ile başlıyor mu? (yabancı uyruklu / YKN)"""
    t = (str(tc) if tc is not None else "").strip()
    return t[:2] in YABANCI_TC_ONEKLERI


def kapsam_gecici_koruma_mi(kapsam_adi) -> bool:
    """Kapsam adı geçici koruma / mülteci / sığınmacı işareti taşıyor mu?"""
    k = _normalize(kapsam_adi)
    return any(anahtar in k for anahtar in GECICI_KORUMA_ANAHTARLARI)


def topkapi_kagit_uyarisi_gerekir_mi(tc, kapsam_adi) -> bool:
    """98/99 ile başlayan (yabancı) AMA geçici koruma kapsamında olmayan →
    'Topkapı SGK'dan kağıt' uyarısı gerekir."""
    return tc_yabanci_mi(tc) and not kapsam_gecici_koruma_mi(kapsam_adi)


def durum_etiketi(tc, kapsam_adi) -> str:
    """Raporlama için sınıf etiketi döndürür."""
    if not tc_yabanci_mi(tc):
        return ""  # yabancı değil — rapor kapsamı dışı
    if kapsam_gecici_koruma_mi(kapsam_adi):
        return "GEÇİCİ KORUMA"
    return "YABANCI SGK'LI — TOPKAPI SGK KAĞIDI GEREKLİ"


# ── Canlı uyarı aç/kapa ayarı (kalıcı, yerel JSON) ──────────────────────
import json as _json
import os as _os

_AYAR_DOSYA = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            "yabanci_hasta_ayar.json")


def uyari_aktif_mi() -> bool:
    """Canlı 'Topkapı SGK kağıdı' uyarı penceresi açık mı? (varsayılan: açık)"""
    try:
        if _os.path.exists(_AYAR_DOSYA):
            with open(_AYAR_DOSYA, "r", encoding="utf-8") as f:
                return bool(_json.load(f).get("canli_uyari_aktif", True))
    except Exception:
        pass
    return True


def uyari_aktif_ayarla(aktif: bool) -> None:
    """Canlı uyarı aç/kapa ayarını yerel JSON'a yaz."""
    try:
        with open(_AYAR_DOSYA, "w", encoding="utf-8") as f:
            _json.dump({"canli_uyari_aktif": bool(aktif)}, f,
                       ensure_ascii=False, indent=2)
    except Exception:
        pass
