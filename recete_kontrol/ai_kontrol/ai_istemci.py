"""Anthropic Claude API İstemcisi (wrapper).

Sistem prompt cache + few-shot + paket JSON → Claude → AISonuc

Hata yönetimi:
    • Anthropic SDK kurulu değilse net hata
    • API key yoksa net hata (ayarlar.api_key_var_mi)
    • KVKK onayı yoksa net hata
    • Limit aşılmışsa net hata
    • Network/rate-limit hatalarında 3x retry (exponential backoff)
    • Sonuç parse hatasında AISonuc(sonuc=HATA) döner
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from . import ai_log_db, ayarlar, prompt_sablonlari, sonuc_parser

logger = logging.getLogger(__name__)


class AIIstemciHata(Exception):
    """Genel AI istemci hatası."""


class APIKeyYok(AIIstemciHata):
    pass


class KVKKOnayiYok(AIIstemciHata):
    pass


class LimitAsildi(AIIstemciHata):
    pass


class SDKYok(AIIstemciHata):
    pass


@dataclass
class CagriIstatistik:
    """Bir AI çağrısının istatistikleri."""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: int = 0
    maliyet_usd: float = 0.0
    model: str = ""


def _anthropic_client():
    """Anthropic SDK client'ı döndür (yoksa SDKYok)."""
    try:
        import anthropic
    except ImportError as e:
        raise SDKYok(
            "Anthropic SDK kurulu değil. "
            "Çözüm: pip install anthropic>=0.40.0"
        ) from e

    cfg = ayarlar.ayarlari_yukle()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise APIKeyYok(
            "Anthropic API anahtarı tanımlı değil. "
            "AI Ayarlar diyaloğundan kendi anahtarınızı girin."
        )
    return anthropic.Anthropic(api_key=api_key)


def _prompt_hash(sistem_text: str, paket_str: str) -> str:
    h = hashlib.sha256()
    h.update(sistem_text.encode("utf-8"))
    h.update(b"|")
    h.update(paket_str.encode("utf-8"))
    return h.hexdigest()[:16]


def kontrol_et(
    paket: Dict[str, Any],
    *,
    model: Optional[str] = None,
    ri_id: str = "",
    log_kaydet: bool = True,
) -> tuple[sonuc_parser.AISonuc, CagriIstatistik]:
    """Bir reçete paketini AI'a gönderip AISonuc döndür.

    Backend ayarına göre yönlendirir:
        • BACKEND_API        → Anthropic SDK + kullanıcının API key'i
        • BACKEND_SUBPROCESS → Yerel `claude` CLI (Max plan ile)

    Args:
        paket: paket_olusturucu.paket_olustur() çıktısı
        model: Override (None → ayarlar.varsayilan_model)
        ri_id: Aylık-tablo satır kimliği (log için)
        log_kaydet: ai_log_db'ye yazılsın mı

    Raises:
        SDKYok, APIKeyYok, KVKKOnayiYok, LimitAsildi
        AIIstemciHata (diğer hatalar)

    Returns:
        (AISonuc, CagriIstatistik)
    """
    if not ayarlar.kvkk_onayli_mi():
        raise KVKKOnayiYok(
            "KVKK onayı verilmedi. AI butonu kullanılmadan önce "
            "hasta verisi anonim formatta AI'a iletilecek onayı verilmelidir."
        )

    asildi, mesaj = ayarlar.limit_asildi_mi()
    if asildi:
        raise LimitAsildi(mesaj)

    cfg = ayarlar.ayarlari_yukle()

    # Backend dispatch
    if cfg.get("backend") == ayarlar.BACKEND_SUBPROCESS:
        from . import claude_code_subprocess
        return claude_code_subprocess.kontrol_et(
            paket, model=model, ri_id=ri_id, log_kaydet=log_kaydet,
        )

    # API backend
    model = model or cfg.get("varsayilan_model") or ayarlar.MODEL_SONNET
    max_tok = int(cfg.get("max_tokens_yaniti") or 4000)

    client = _anthropic_client()

    klinik_iste = bool(cfg.get("klinik_yorum_iste", True))
    sistem_blok = prompt_sablonlari.sistem_mesaj_blogu(cache=True)
    fewshot = prompt_sablonlari.fewshot_mesajlari()
    kullanici_mesaj = prompt_sablonlari.kullanici_mesaji_olustur(
        paket, klinik_yorum_iste=klinik_iste)
    mesajlar = fewshot + [{"role": "user", "content": kullanici_mesaj}]

    p_hash = _prompt_hash(sistem_blok["text"], kullanici_mesaj)
    recete_no = ((paket.get("recete") or {}).get("recete_no") or "")
    ilac_adi = (((paket.get("recete") or {}).get("ilac") or {}).get("urun_adi") or "")
    hasta_tc_hash = ((paket.get("hasta") or {}).get("tc_hash") or "")
    sut_madde = (paket.get("rapor") or {}).get("rapor_kodu") if paket.get("rapor") else ""

    t0 = time.time()
    cevap_text = ""
    hata_metni = ""
    istat = CagriIstatistik(model=model)
    parse_sonuc = sonuc_parser.AISonuc(sonuc=sonuc_parser.SONUC_HATA)

    son_hata: Optional[Exception] = None
    for deneme in range(3):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tok,
                system=[sistem_blok],
                messages=mesajlar,
            )
            # Cevap parse
            try:
                cevap_text = "".join(
                    blok.text for blok in resp.content
                    if getattr(blok, "type", "") == "text"
                )
            except Exception as e_parse:
                cevap_text = str(resp.content)
                logger.warning("Cevap text birleştirme hatası: %s", e_parse)

            # Token istatistikleri
            try:
                usage = resp.usage
                istat.input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
                istat.output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
                istat.cached_input_tokens = int(
                    getattr(usage, "cache_read_input_tokens", 0) or 0)
                istat.cache_write_tokens = int(
                    getattr(usage, "cache_creation_input_tokens", 0) or 0)
            except Exception:
                pass

            istat.latency_ms = int((time.time() - t0) * 1000)
            istat.maliyet_usd = ayarlar.maliyet_hesapla(
                model,
                istat.input_tokens,
                istat.output_tokens,
                istat.cached_input_tokens,
                istat.cache_write_tokens,
            )
            son_hata = None
            break
        except Exception as e:
            son_hata = e
            tip = type(e).__name__
            mesaj = str(e)
            logger.warning(
                "AI çağrı denemesi %d/%d başarısız (%s): %s",
                deneme + 1, 3, tip, mesaj[:200],
            )
            # Rate-limit / overloaded → bekle, devam et
            geciktirilebilir = (
                "RateLimitError" in tip
                or "OverloadedError" in tip
                or "APIConnectionError" in tip
                or "APITimeoutError" in tip
                or "529" in mesaj
                or "429" in mesaj
            )
            if not geciktirilebilir or deneme >= 2:
                break
            time.sleep(2 ** deneme)

    if son_hata is not None:
        hata_metni = f"{type(son_hata).__name__}: {son_hata}"
        parse_sonuc.hata = hata_metni
    else:
        # paket'i parser'a geçir → AI YETERSIZ_VERI denerse veya ozet boşsa
        # paket.veri_kapsami'ndan eksik alanlar otomatik enjekte edilir
        # (kullanıcı talebi 2026-05-21: "yetersiz veri demek yerine
        # neden anlatsın").
        parse_sonuc = sonuc_parser.parse(cevap_text, paket=paket)

    if log_kaydet:
        try:
            ai_log_db.cagri_kaydet(
                ri_id=ri_id,
                hasta_tc=hasta_tc_hash,   # zaten hashlenmiş (paket'ten)
                recete_no=recete_no,
                ilac_adi=ilac_adi,
                sut_madde=str(sut_madde or ""),
                model=model,
                input_tokens=istat.input_tokens,
                output_tokens=istat.output_tokens,
                cached_input_tokens=istat.cached_input_tokens,
                cache_write_tokens=istat.cache_write_tokens,
                maliyet_usd=istat.maliyet_usd,
                latency_ms=istat.latency_ms,
                sonuc_etiketi=parse_sonuc.sonuc,
                guven_skoru=parse_sonuc.guven_skoru,
                prompt_hash=p_hash,
                cevap_text=cevap_text,
                hata=hata_metni or parse_sonuc.hata,
            )
        except Exception as e_log:
            logger.warning("AI log kaydı atlandı: %s", e_log)

    if son_hata is not None:
        raise AIIstemciHata(hata_metni)

    return parse_sonuc, istat


def baglanti_test_et(model: Optional[str] = None) -> tuple[bool, str]:
    """Aktif backend'in çalışıp çalışmadığını basit bir ping ile test et.

    Returns: (basari, mesaj)
    """
    cfg = ayarlar.ayarlari_yukle()

    # Subprocess backend
    if cfg.get("backend") == ayarlar.BACKEND_SUBPROCESS:
        from . import claude_code_subprocess
        return claude_code_subprocess.baglanti_test_et(model=model)

    # API backend
    try:
        client = _anthropic_client()
    except Exception as e:
        return False, str(e)

    m = model or cfg.get("varsayilan_model") or ayarlar.MODEL_SONNET
    try:
        resp = client.messages.create(
            model=m,
            max_tokens=20,
            messages=[{"role": "user", "content": "Test. Sadece 'OK' yaz."}],
        )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        )
        return True, f"API bağlantısı OK ({m}): {text.strip()[:50]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
