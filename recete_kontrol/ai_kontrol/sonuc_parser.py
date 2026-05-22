"""AI Cevabı Parser — Claude'dan dönen text'i JSON'a çevir + valide et.

AI cevabı her zaman JSON formatında olmalı (sistem prompt'ta zorunlu).
Bu modül:
  • Cevap text'inden JSON çıkarır (markdown code-block içinde olabilir)
  • Şemayı validate eder (sonuc enum, guven 0-1, liste tipleri)
  • Eksik/bozuk alanları KONTROL_EDILEMEDI'ye düşürür
  • UI'a yansıtılacak özet + detay metni üretir
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Sonuç etiketleri (CLAUDE.md SUT disiplini ile uyumlu)
SONUC_UYGUN = "UYGUN"
SONUC_UYGUN_DEGIL = "UYGUN_DEGIL"
SONUC_SUPHELI = "SUPHELI"
SONUC_KONTROL_EDILEMEDI = "KONTROL_EDILEMEDI"
SONUC_YETERSIZ_VERI = "YETERSIZ_VERI"
SONUC_MANUEL = "MANUEL_KONTROL_GEREKIR"
SONUC_HATA = "HATA"

GECERLI_SONUCLAR = (
    SONUC_UYGUN, SONUC_UYGUN_DEGIL, SONUC_SUPHELI,
    SONUC_KONTROL_EDILEMEDI, SONUC_YETERSIZ_VERI, SONUC_MANUEL,
)

# Sonuç → kısa Türkçe etiket (UI sütun değeri)
ETIKET_KISA = {
    SONUC_UYGUN: "UYGUN",
    SONUC_UYGUN_DEGIL: "UYGUN DEĞİL",
    SONUC_SUPHELI: "ŞÜPHELİ",
    SONUC_KONTROL_EDILEMEDI: "KONTROL EDİLEMEDİ",
    SONUC_YETERSIZ_VERI: "YETERSİZ VERİ",
    SONUC_MANUEL: "MANUEL KONTROL",
    SONUC_HATA: "AI HATA",
}

# Sonuç → tablo arka plan rengi (aylik_recete_sorgu_gui.RENK_* ile uyumlu)
SONUC_RENK = {
    SONUC_UYGUN: "yesil",
    SONUC_UYGUN_DEGIL: "kirmizi",
    SONUC_SUPHELI: "sari",
    SONUC_KONTROL_EDILEMEDI: "sari",
    SONUC_YETERSIZ_VERI: "turuncu",
    SONUC_MANUEL: "turuncu",
    SONUC_HATA: "turuncu",
}


@dataclass
class AISonuc:
    """AI'dan dönen yapılandırılmış sonuç."""
    sonuc: str = SONUC_HATA
    guven_skoru: float = 0.0
    sut_referans: str = ""
    saglanan_sartlar: List[str] = field(default_factory=list)
    saglanmayan_sartlar: List[Dict[str, str]] = field(default_factory=list)
    kontrol_edilemeyen_sartlar: List[Dict[str, str]] = field(default_factory=list)
    ozet_aciklama: str = ""
    detay_rapor: str = ""
    # Klinik yorum — uzun, serbest tonlu, doktor sohbeti benzeri
    # bütünsel analiz. AI çubuğuna sorulmuş gibi açık uçlu cevap.
    klinik_yorum: str = ""
    ham_cevap: str = ""
    hata: str = ""

    @property
    def etiket(self) -> str:
        return ETIKET_KISA.get(self.sonuc, self.sonuc)

    @property
    def renk(self) -> str:
        return SONUC_RENK.get(self.sonuc, "beyaz")

    def aciklama_metni(self) -> str:
        """UI'a yazılacak tam açıklama metni (özet + sağlanan/sağlanmayan/KE)."""
        satirlar: List[str] = []
        if self.ozet_aciklama:
            satirlar.append(self.ozet_aciklama.strip())
            satirlar.append("")
        if self.sut_referans:
            satirlar.append(f"SUT: {self.sut_referans}")
            satirlar.append("")
        if self.saglanan_sartlar:
            satirlar.append("✓ Sağlanan şartlar:")
            for s in self.saglanan_sartlar:
                satirlar.append(f"  • {s}")
            satirlar.append("")
        if self.saglanmayan_sartlar:
            satirlar.append("✗ Sağlanmayan şartlar:")
            for s in self.saglanmayan_sartlar:
                ad = s.get("sart", "")
                neden = s.get("neden", "")
                if neden:
                    satirlar.append(f"  • {ad} — {neden}")
                else:
                    satirlar.append(f"  • {ad}")
            satirlar.append("")
        if self.kontrol_edilemeyen_sartlar:
            satirlar.append("? Kontrol edilemeyen şartlar (manuel doğrula):")
            for s in self.kontrol_edilemeyen_sartlar:
                ad = s.get("sart", "")
                eksik = s.get("eksik_veri", "")
                if eksik:
                    satirlar.append(f"  • {ad} — {eksik}")
                else:
                    satirlar.append(f"  • {ad}")
            satirlar.append("")
        satirlar.append(f"Genel sonuç: {self.etiket}")
        if self.guven_skoru:
            satirlar.append(f"Güven: %{int(self.guven_skoru * 100)}")
        if self.detay_rapor:
            satirlar.append("")
            satirlar.append("— Teknik Detay —")
            satirlar.append(self.detay_rapor.strip())
        if self.klinik_yorum:
            satirlar.append("")
            satirlar.append("═══ Klinik Yorum (AI bütünsel analiz) ═══")
            satirlar.append(self.klinik_yorum.strip())
        return "\n".join(satirlar)


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _json_cikart(text: str) -> Optional[str]:
    """AI cevabından JSON bloğunu çıkar (markdown fence veya raw)."""
    if not text:
        return None
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1)
    m2 = _JSON_BLOCK_RE.search(text)
    if m2:
        return m2.group(0)
    return None


def _normalize_sonuc(s: Any) -> str:
    """Sonuç string'ini geçerli enum'a normalize et."""
    if not s:
        return SONUC_HATA
    t = str(s).strip().upper().replace(" ", "_").replace("Ğ", "G").replace("İ", "I").replace("Ş", "S")
    # Yaygın varyasyonlar.
    # NOT (2026-05-21): "YETERSIZ_VERI" / "VERI_EKSIK" sistem prompt'tan
    # tamamen kaldırıldı (kullanıcı talebi — etiket bilgi vermiyor, eczacıyı
    # boşluğa düşürüyordu). Geri uyumluluk için AI hala dönerse otomatik
    # SUPHELI'ye çevriliyor; worker tarafında paket veri_kapsami'ndan eksik
    # alanlar ozet_aciklama'ya enjekte ediliyor.
    aliaslar = {
        "UYGUNDUR": SONUC_UYGUN,
        "UYGUN_DEGILDIR": SONUC_UYGUN_DEGIL,
        "UYGUN_DEGIL": SONUC_UYGUN_DEGIL,
        "UYGUN_DEĞIL": SONUC_UYGUN_DEGIL,
        "SUPHELI": SONUC_SUPHELI,
        "ŞUPHELI": SONUC_SUPHELI,
        "SARTLI_UYGUN": SONUC_SUPHELI,
        "SARTLİ_UYGUN": SONUC_SUPHELI,
        "BELIRSIZ": SONUC_KONTROL_EDILEMEDI,
        "KONTROL_EDILEMEDI": SONUC_KONTROL_EDILEMEDI,
        # Geri uyumluluk: eski AI cevapları YETERSIZ_VERI dönerse SUPHELI'ye çevir
        "YETERSIZ_VERI": SONUC_SUPHELI,
        "VERI_EKSIK": SONUC_SUPHELI,
        "INSUFFICIENT_DATA": SONUC_SUPHELI,
        "MANUEL": SONUC_MANUEL,
        "MANUEL_KONTROL": SONUC_MANUEL,
        "MANUEL_KONTROL_GEREKIR": SONUC_MANUEL,
    }
    if t in aliaslar:
        return aliaslar[t]
    if t in GECERLI_SONUCLAR:
        return t
    return SONUC_KONTROL_EDILEMEDI


def _liste_dict_normalize(lst: Any, key1: str, key2: str) -> List[Dict[str, str]]:
    """Şart listelerini [{key1: ..., key2: ...}, ...] formatına normalize et."""
    if not lst:
        return []
    out: List[Dict[str, str]] = []
    for item in lst:
        if isinstance(item, dict):
            out.append({
                key1: str(item.get(key1, "") or item.get("ad", "") or ""),
                key2: str(item.get(key2, "") or ""),
            })
        elif isinstance(item, str):
            out.append({key1: item, key2: ""})
    return out


def _liste_str_normalize(lst: Any) -> List[str]:
    """Sağlanan şartlar gibi düz string listelerini normalize et."""
    if not lst:
        return []
    out: List[str] = []
    for item in lst:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            ad = item.get("sart") or item.get("ad") or item.get("name") or ""
            if ad:
                out.append(str(ad))
    return out


def parse(ai_text: str, paket: Optional[Dict[str, Any]] = None) -> AISonuc:
    """AI cevap text'ini AISonuc'a çevir.

    Args:
        ai_text: Claude'dan dönen ham text (JSON içerir).
        paket: Opsiyonel — AI'a gönderilen orijinal paket. Verilirse, AI'ın
               açıklama boş bıraktığı veya YETERSIZ_VERI dönerek SUPHELI'ye
               çevrildiği durumlarda paket.veri_kapsami'ndan hangi alanların
               eksik olduğu otomatik enjekte edilir (kullanıcı "neden ŞÜPHELİ"
               sorduğunda gerekçeyi görsün diye).

    Returns:
        AISonuc — başarısızlık durumunda sonuc=HATA + hata mesajı dolu.
    """
    sonuc = AISonuc(ham_cevap=ai_text or "")
    json_str = _json_cikart(ai_text or "")
    if not json_str:
        sonuc.hata = "AI cevabında JSON bloğu bulunamadı"
        return sonuc
    try:
        veri = json.loads(json_str)
    except Exception as e:
        sonuc.hata = f"JSON parse hatası: {e}"
        return sonuc
    if not isinstance(veri, dict):
        sonuc.hata = f"JSON dict değil: {type(veri).__name__}"
        return sonuc

    ham_sonuc = str(veri.get("sonuc") or "").strip().upper()
    sonuc.sonuc = _normalize_sonuc(veri.get("sonuc"))
    yetersiz_veri_alias = ham_sonuc in (
        "YETERSIZ_VERI", "YETERSİZ_VERI", "VERI_EKSIK", "INSUFFICIENT_DATA")
    try:
        gv = float(veri.get("guven_skoru", 0) or 0)
        sonuc.guven_skoru = max(0.0, min(1.0, gv))
    except (TypeError, ValueError):
        sonuc.guven_skoru = 0.0
    sonuc.sut_referans = str(veri.get("sut_referans") or "")
    sonuc.saglanan_sartlar = _liste_str_normalize(veri.get("saglanan_sartlar"))
    sonuc.saglanmayan_sartlar = _liste_dict_normalize(
        veri.get("saglanmayan_sartlar"), "sart", "neden"
    )
    sonuc.kontrol_edilemeyen_sartlar = _liste_dict_normalize(
        veri.get("kontrol_edilemeyen_sartlar"), "sart", "eksik_veri"
    )
    sonuc.ozet_aciklama = str(veri.get("ozet_aciklama") or "").strip()
    sonuc.detay_rapor = str(veri.get("detay_rapor") or "").strip()
    # Serbest klinik yorum (sohbet tonu, uzun analiz)
    sonuc.klinik_yorum = str(
        veri.get("klinik_yorum") or veri.get("klinik_analiz")
        or veri.get("ek_yorum") or ""
    ).strip()

    # AI YETERSIZ_VERI dönerek SUPHELI'ye çevrildiyse VEYA özet boşsa,
    # paket veri_kapsami'ndan eksik alanlara işaret eden otomatik açıklama
    # üret (kullanıcı "neden ŞÜPHELİ" diye sorduğunda gerekçe görsün).
    if paket and (yetersiz_veri_alias or not sonuc.ozet_aciklama):
        eksik_aciklama = _eksik_alanlar_aciklamasi(paket)
        if eksik_aciklama:
            on_ek = ("AI YETERSIZ_VERI etiketi denedi (artık yasak — "
                     "SUPHELI'ye çevrildi). "
                     if yetersiz_veri_alias else "")
            if sonuc.ozet_aciklama:
                sonuc.ozet_aciklama = (
                    f"{on_ek}{sonuc.ozet_aciklama}\n\n{eksik_aciklama}")
            else:
                sonuc.ozet_aciklama = f"{on_ek}{eksik_aciklama}"

    if sonuc.sonuc == SONUC_HATA:
        sonuc.hata = "AI sonucu tanınamadı"
    return sonuc


def _eksik_alanlar_aciklamasi(paket: Dict[str, Any]) -> str:
    """Paket'in veri_kapsami özetinden eksik alanları insan-okunur şekilde
    listele. AI ozet vermediğinde kullanıcının 'neden ŞÜPHELİ' sorusuna
    yanıt olarak ozet_aciklama'ya enjekte edilir.

    Returns: "Eksik alanlar (AI değerlendirmeyi sınırladı): ..." formatlı
             metin, hiç eksik yoksa boş string.
    """
    vk = paket.get("veri_kapsami") or {}
    if not isinstance(vk, dict):
        return ""

    bos_alanlar = []
    if not vk.get("ilac_adi_var"): bos_alanlar.append("ilaç adı")
    if not vk.get("atc_kodu_var"): bos_alanlar.append("ATC kodu")
    if not vk.get("recete_teshis_var"): bos_alanlar.append("reçete teşhisi")
    if not vk.get("rapor_var"):
        bos_alanlar.append("rapor (eşleşen rapor bulunamadı)")
    else:
        if not vk.get("rapor_kodu_var"):
            bos_alanlar.append("rapor kodu")
        if vk.get("rapor_metni_uzunluk", 0) < 20:
            bos_alanlar.append(
                f"rapor metni ({vk.get('rapor_metni_uzunluk', 0)} karakter)")
        if vk.get("rapor_icd_sayisi", 0) == 0:
            bos_alanlar.append("rapor ICD listesi")
        if vk.get("rapor_etken_madde_sayisi", 0) == 0:
            bos_alanlar.append("rapor etken madde listesi")
    if not vk.get("hasta_yasi_var"): bos_alanlar.append("hasta yaşı")
    if not vk.get("hasta_cinsiyet_var"): bos_alanlar.append("hasta cinsiyeti")
    if vk.get("hasta_diger_rapor_sayisi", 0) == 0:
        bos_alanlar.append("hasta diğer raporları")
    if vk.get("hasta_ilac_gecmisi_sayisi", 0) == 0:
        bos_alanlar.append("hasta ilaç geçmişi")

    if not bos_alanlar:
        return ""
    return ("Eksik/sınırlı veri (AI değerlendirmeyi sınırladı): "
            + ", ".join(bos_alanlar)
            + ". → Paket Önizle dialogundan tam paketi inceleyebilirsin.")
