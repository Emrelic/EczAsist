"""AI Kontrol Ayarları — kullanıcı yapılandırması (ai_config.json).

Her kullanıcı **kendi** Anthropic API anahtarını girer (CLAUDE.md uyumlu;
bizim anahtar gömülü değil). Yapılandırma `ai_config.json` dosyasında
saklanır ve .gitignore'a düşer.

Şema (ai_config.json):
{
    "api_key": "sk-ant-...",
    "varsayilan_model": "claude-sonnet-4-6",
    "gunluk_cagri_limiti": 100,
    "gunluk_maliyet_limiti_usd": 5.0,
    "kvkk_onay": true,
    "kvkk_onay_tarih": "2026-05-21T10:00:00",
    "max_tokens_yaniti": 4000
}
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Anthropic model kimlikleri (CLAUDE.md system prompt'ta belirtilenler)
MODEL_OPUS = "claude-opus-4-7"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_HAIKU = "claude-haiku-4-5-20251001"

GECERLI_MODELLER = (MODEL_OPUS, MODEL_SONNET, MODEL_HAIKU)

MODEL_ETIKETLERI = {
    MODEL_OPUS:   "Opus 4.7 (en kaliteli, ~5x maliyet)",
    MODEL_SONNET: "Sonnet 4.6 (dengeli, hız+kalite — varsayılan)",
    MODEL_HAIKU:  "Haiku 4.5 (en hızlı/ucuz, basit kontrollere)",
}

# Modele göre USD/1M token fiyatları (2026-05; resmi Anthropic fiyat listesi)
# Cache okuma %90 ucuz; cache yazma 1.25x. Output ~5x input.
FIYAT_USD_PER_MTOK = {
    MODEL_OPUS:   {"input": 15.00, "output": 75.00,
                    "cache_read": 1.50, "cache_write": 18.75},
    MODEL_SONNET: {"input": 3.00,  "output": 15.00,
                    "cache_read": 0.30, "cache_write": 3.75},
    MODEL_HAIKU:  {"input": 1.00,  "output": 5.00,
                    "cache_read": 0.10, "cache_write": 1.25},
}

# Backend seçenekleri
BACKEND_API = "api"               # Anthropic SDK + kullanıcının API key'i (varsayılan)
BACKEND_SUBPROCESS = "subprocess" # Yerel `claude` CLI subprocess (Max plan ile çalışır)

GECERLI_BACKENDLER = (BACKEND_API, BACKEND_SUBPROCESS)

BACKEND_ETIKETLERI = {
    BACKEND_API: "Anthropic API (kendi API anahtarınız)",
    BACKEND_SUBPROCESS: "Claude Code subprocess (Max planınızı kullanır)",
}

VARSAYILAN_AYARLAR: Dict[str, Any] = {
    "backend": BACKEND_API,
    "api_key": "",
    "varsayilan_model": MODEL_SONNET,
    "gunluk_cagri_limiti": 100,
    "gunluk_maliyet_limiti_usd": 5.0,
    "kvkk_onay": False,
    "kvkk_onay_tarih": "",
    "max_tokens_yaniti": 8000,           # klinik_yorum için arttırıldı
    "klinik_yorum_iste": True,           # AI'dan uzun klinik analiz iste
    "subprocess_timeout_sn": 600,        # subprocess timeout (kombi ilaçlar için)
}


def _config_yolu() -> Path:
    """ai_config.json yolunu döndür (proje kökü)."""
    proje_kok = Path(__file__).resolve().parents[2]
    return proje_kok / "ai_config.json"


def ayarlari_yukle() -> Dict[str, Any]:
    """Mevcut ayarları yükle, dosya yoksa varsayılan döndür."""
    yol = _config_yolu()
    if not yol.exists():
        return dict(VARSAYILAN_AYARLAR)
    try:
        with open(yol, "r", encoding="utf-8") as f:
            veri = json.load(f) or {}
    except Exception as e:
        logger.error("ai_config.json okunamadı: %s", e)
        return dict(VARSAYILAN_AYARLAR)

    sonuc = dict(VARSAYILAN_AYARLAR)
    sonuc.update({k: v for k, v in veri.items() if k in VARSAYILAN_AYARLAR})
    if sonuc.get("varsayilan_model") not in GECERLI_MODELLER:
        sonuc["varsayilan_model"] = MODEL_SONNET
    if sonuc.get("backend") not in GECERLI_BACKENDLER:
        sonuc["backend"] = BACKEND_API
    return sonuc


def backend_subprocess_mu() -> bool:
    """Aktif backend Claude Code subprocess mı?"""
    return ayarlari_yukle().get("backend") == BACKEND_SUBPROCESS


def api_key_var_mi() -> bool:
    """API key tanımlı mı? (Subprocess mode'da gerekli değil)"""
    cfg = ayarlari_yukle()
    if cfg.get("backend") == BACKEND_SUBPROCESS:
        return True  # subprocess mode'da API key gerekmez
    return bool((cfg.get("api_key") or "").strip())


def ayarlari_kaydet(ayarlar: Dict[str, Any]) -> bool:
    """Ayarları ai_config.json'a yaz."""
    yol = _config_yolu()
    try:
        mevcut = ayarlari_yukle()
        mevcut.update({k: v for k, v in ayarlar.items() if k in VARSAYILAN_AYARLAR})
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(mevcut, f, indent=2, ensure_ascii=False)
        try:
            os.chmod(yol, 0o600)
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error("ai_config.json yazılamadı: %s", e)
        return False


def kvkk_onayli_mi() -> bool:
    """KVKK onayı verildi mi?"""
    ayarlar = ayarlari_yukle()
    return bool(ayarlar.get("kvkk_onay"))


def kvkk_onay_ver() -> bool:
    """KVKK onayını kalıcı kaydet."""
    ayarlar = ayarlari_yukle()
    ayarlar["kvkk_onay"] = True
    ayarlar["kvkk_onay_tarih"] = datetime.now().isoformat(timespec="seconds")
    return ayarlari_kaydet(ayarlar)


def maliyet_hesapla(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Bir AI çağrısının USD cinsinden tahmini maliyetini hesapla."""
    fiyat = FIYAT_USD_PER_MTOK.get(model)
    if not fiyat:
        return 0.0
    M = 1_000_000.0
    inp_normal = max(0, int(input_tokens) - int(cached_input_tokens) - int(cache_write_tokens))
    toplam = (
        (inp_normal * fiyat["input"]) / M
        + (int(cached_input_tokens) * fiyat["cache_read"]) / M
        + (int(cache_write_tokens) * fiyat["cache_write"]) / M
        + (int(output_tokens) * fiyat["output"]) / M
    )
    return round(toplam, 6)


def limit_asildi_mi() -> tuple[bool, str]:
    """Günlük çağrı/maliyet limitlerinin aşılıp aşılmadığını döndür.

    Returns: (asildi, sebep_mesaji)
    """
    from . import ai_log_db
    ayarlar = ayarlari_yukle()
    ozet = ai_log_db.gunluk_ozet()
    cagri_lim = int(ayarlar.get("gunluk_cagri_limiti") or 0)
    maliyet_lim = float(ayarlar.get("gunluk_maliyet_limiti_usd") or 0.0)

    if cagri_lim > 0 and ozet.get("cagri_sayisi", 0) >= cagri_lim:
        return True, (
            f"Günlük çağrı limiti aşıldı: "
            f"{ozet['cagri_sayisi']}/{cagri_lim}. "
            f"Ayarlar'dan limiti artırabilirsiniz."
        )
    if maliyet_lim > 0 and ozet.get("maliyet_usd", 0.0) >= maliyet_lim:
        return True, (
            f"Günlük maliyet limiti aşıldı: "
            f"${ozet['maliyet_usd']:.4f} / ${maliyet_lim:.2f}. "
            f"Ayarlar'dan limiti artırabilirsiniz."
        )
    return False, ""
