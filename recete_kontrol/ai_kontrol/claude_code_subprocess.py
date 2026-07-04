"""Claude Code Subprocess Backend (Anthropic API key alternatifi).

Kullanıcı Anthropic Max planı sahibi ise, kendi API anahtarı yerine
yerel `claude` CLI'ı subprocess olarak çağırabilir. Bu:
    • Max abonelik üzerinden çalışır (ek fatura yok)
    • API key gerektirmez
    • `total_cost_usd` raporlanır AMA Max'te ücretsiz (sadece metric)
    • `--tools ""` ile saf JSON cevap döner

Komut formatı:
    claude -p --output-format json --tools "" --model <sonnet|opus|haiku>
    < <full_prompt_via_stdin>

Çıktı: JSON object — `result` alanında Claude'un text cevabı (JSON olmalı).
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# Windows: claude CLI subprocess'ini başlatırken konsol penceresi açılmasın
# (pythonw.exe altında çalışıyor olsak bile node.js .exe için cmd penceresi
# pop edebiliyor — kullanıcıya "siyah ekran" olarak görünüyor).
_SUBPROCESS_KWARGS: Dict[str, Any] = {}
if sys.platform == "win32":
    _SUBPROCESS_KWARGS["creationflags"] = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    )

from . import ai_log_db, ayarlar, prompt_sablonlari, sonuc_parser

logger = logging.getLogger(__name__)

# Subprocess timeout (saniye).
# Pratik gözlem (2026-05-21): klinik_yorum + geçmiş rapor zenginleştirme sonrası
# basit reçete ~60-90 sn, kombi/karmaşık ilaç (3'lü antihipertansif, hepatit
# atomik vs.) 180+ sn'ye çıkabiliyor. 600s güvenli üst sınır.
VARSAYILAN_TIMEOUT_SN = 600


class ClaudeCodeYok(Exception):
    """`claude` komutu sistemde bulunamadı."""


class SubprocessHata(Exception):
    """Subprocess çağrısı başarısız / çıktı parse edilemedi."""


# ──────────────────────────────────────────────────────────────────────
# YARDIMCILAR — komut tespit + sağlık
# ──────────────────────────────────────────────────────────────────────

def claude_komutu_bul() -> Optional[str]:
    """Yerel `claude` CLI'ın tam yolunu döndür (PATH'ten)."""
    return shutil.which("claude")


_NOTR_DIZIN: Optional[str] = None


def _notr_calisma_dizini() -> str:
    """CLAUDE.md içermeyen boş, kalıcı bir geçici dizin (tek sefer yaratılır).

    `claude -p` subprocess'i bu dizinde çalışır; proje kökündeki CLAUDE.md +
    araçlar yüklenmez → model saf JSON döndürür (ajanca davranmaz). Tek dizin
    tekrar kullanılır (her çağrıda yeni dizin birikmesin)."""
    global _NOTR_DIZIN
    if _NOTR_DIZIN and Path(_NOTR_DIZIN).is_dir():
        return _NOTR_DIZIN
    import tempfile
    _NOTR_DIZIN = tempfile.mkdtemp(prefix="eczasist_ai_")
    return _NOTR_DIZIN


def saglik_kontrolu() -> tuple[bool, str]:
    """`claude --version` çıktısını al. UI'da durum etiketi için."""
    yol = claude_komutu_bul()
    if not yol:
        return False, (
            "claude komutu PATH'te bulunamadı.\n"
            "Çözüm: Claude Code yüklü değilse https://claude.com/claude-code "
            "adresinden indirin; yüklüyse `where claude` ile yolu kontrol edin."
        )
    try:
        proc = subprocess.run(
            [yol, "--version"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
            **_SUBPROCESS_KWARGS,
        )
        if proc.returncode != 0:
            return False, f"`claude --version` hata kodu {proc.returncode}: {proc.stderr[:200]}"
        return True, f"{yol} → {(proc.stdout or '').strip()[:80]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ──────────────────────────────────────────────────────────────────────
# SUBPROCESS ÇAĞRISI
# ──────────────────────────────────────────────────────────────────────

@dataclass
class SubprocessCevap:
    result_text: str                # Claude'un cevap metni (JSON içerir)
    total_cost_usd: float = 0.0     # Max plan: metric, fatura edilmez
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    session_id: str = ""
    raw_json: Optional[Dict[str, Any]] = None


def _model_alias(tam_id: str) -> str:
    """Tam model ID'sini claude CLI alias'ına çevir."""
    eşleme = {
        ayarlar.MODEL_SONNET: "sonnet",
        ayarlar.MODEL_OPUS: "opus",
        ayarlar.MODEL_HAIKU: "haiku",
    }
    return eşleme.get(tam_id, tam_id)


def subprocess_cagir(
    full_prompt: str,
    *,
    model: Optional[str] = None,
    timeout: int = VARSAYILAN_TIMEOUT_SN,
    cwd: Optional[str] = None,
) -> SubprocessCevap:
    """`claude -p --output-format json` çağrısı yapıp cevabı parse et.

    Args:
        full_prompt: Stdin'den verilecek tam prompt (sistem+fewshot+paket)
        model: 'sonnet' / 'opus' / 'haiku' (None → claude default)
        timeout: saniye
        cwd: çalışma dizini (None → mevcut)

    Raises:
        ClaudeCodeYok    — komut bulunamadı
        SubprocessHata   — çağrı/parse hatası
    """
    yol = claude_komutu_bul()
    if not yol:
        raise ClaudeCodeYok(
            "claude komutu PATH'te bulunamadı. Claude Code yüklü mü?"
        )

    # `--tools ""`  → Bash/Edit/Read araçlarını kapat; sadece text üretsin
    # `--bare`'i KULLANMA — Max plan OAuth'unu engeller (sadece API key tanır)
    cmd = [yol, "-p", "--output-format", "json", "--tools", ""]
    if model:
        cmd.extend(["--model", model])

    # KRİTİK: subprocess'i proje kökünde çalıştırma! Proje kökünde `claude`,
    # projenin CLAUDE.md'sini (~47k token SUT talimatı) + araçları yükler ve
    # model saf JSON döndürmek yerine Claude Code ajanı gibi davranıp dosya
    # grep'lemeye kalkar → "AI cevabında JSON bloğu bulunamadı" hatası
    # (SUZAN OLGAÇ 2O12S2H pilotu, 2026-07-04; proje kökü cache_write=52k,
    # nötr dizin=5.6k). Nötr, boş bir geçici dizinde çalıştır → CLAUDE.md yok.
    if not cwd:
        cwd = _notr_calisma_dizini()

    logger.info("claude subprocess çağrısı: model=%s prompt_chars=%d cwd=%s",
                model or "(default)", len(full_prompt), cwd)

    try:
        proc = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            shell=False,
            **_SUBPROCESS_KWARGS,
        )
    except subprocess.TimeoutExpired:
        raise SubprocessHata(
            f"Subprocess timeout ({timeout}s) — claude cevap vermedi."
        )
    except FileNotFoundError as e:
        raise ClaudeCodeYok(f"claude komutu çalıştırılamadı: {e}")
    except Exception as e:
        raise SubprocessHata(f"Subprocess hatası: {type(e).__name__}: {e}")

    if proc.returncode != 0:
        raise SubprocessHata(
            f"claude exit={proc.returncode}\n"
            f"stderr: {(proc.stderr or '')[:500]}\n"
            f"stdout[:200]: {(proc.stdout or '')[:200]}"
        )

    stdout = proc.stdout or ""
    if not stdout.strip():
        raise SubprocessHata("claude boş stdout döndü.")

    try:
        veri = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise SubprocessHata(
            f"Subprocess JSON parse hatası: {e}\nstdout[:500]: {stdout[:500]}"
        )

    if not isinstance(veri, dict):
        raise SubprocessHata(f"Subprocess çıktısı dict değil: {type(veri).__name__}")

    if veri.get("is_error"):
        raise SubprocessHata(
            f"claude error subtype={veri.get('subtype', '')!r}: "
            f"{(veri.get('result', '') or '')[:300]}"
        )

    usage = veri.get("usage") or {}
    return SubprocessCevap(
        result_text=str(veri.get("result") or ""),
        total_cost_usd=float(veri.get("total_cost_usd") or 0.0),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cache_read_tokens=int(usage.get("cache_read_input_tokens") or 0),
        cache_creation_tokens=int(usage.get("cache_creation_input_tokens") or 0),
        duration_ms=int(veri.get("duration_ms") or 0),
        session_id=str(veri.get("session_id") or ""),
        raw_json=veri,
    )


# ──────────────────────────────────────────────────────────────────────
# ANA İSTEMCİ — ai_istemci.kontrol_et ile aynı imza
# ──────────────────────────────────────────────────────────────────────

def _full_prompt_olustur(paket: Dict[str, Any],
                          klinik_yorum_iste: bool = True) -> str:
    """Sistem prompt + few-shot + kullanıcı paketi → tek string."""
    sistem = prompt_sablonlari.SISTEM_PROMPT

    fewshot_bloklari = []
    for ornek in prompt_sablonlari.FEWSHOT_ORNEKLERI:
        etiket = ("[ÖRNEK — KULLANICI MESAJI]" if ornek["rol"] == "kullanici"
                  else "[ÖRNEK — ASİSTAN CEVABI]")
        fewshot_bloklari.append(f"{etiket}\n{ornek['icerik']}")
    fewshot_metni = "\n\n".join(fewshot_bloklari)

    kullanici = prompt_sablonlari.kullanici_mesaji_olustur(
        paket, klinik_yorum_iste=klinik_yorum_iste)

    return (
        "=== SİSTEM TALİMATLARI ===\n"
        f"{sistem}\n\n"
        "=== ÖRNEKLER (yukarıdaki şemaya uygun) ===\n"
        f"{fewshot_metni}\n\n"
        "=== ŞİMDİKİ GÖREV ===\n"
        f"{kullanici}\n\n"
        "Cevabını **sadece JSON olarak** ver. Başka açıklama, "
        "markdown fence (```) veya konuşma metni KOYMA — pür JSON."
    )


def kontrol_et(
    paket: Dict[str, Any],
    *,
    model: Optional[str] = None,
    ri_id: str = "",
    log_kaydet: bool = True,
) -> tuple[sonuc_parser.AISonuc, "Any"]:
    """`ai_istemci.kontrol_et` ile aynı imzaya sahip subprocess versiyonu.

    Returns: (AISonuc, CagriIstatistik) — `ai_istemci.CagriIstatistik` döner.
    """
    # Geç import — circular'ı önle
    from .ai_istemci import AIIstemciHata, CagriIstatistik

    cfg = ayarlar.ayarlari_yukle()
    if not ayarlar.kvkk_onayli_mi():
        # ai_istemci'deki ile aynı disiplin
        from .ai_istemci import KVKKOnayiYok
        raise KVKKOnayiYok(
            "KVKK onayı verilmedi. Subprocess mode'da da hasta verisi "
            "Anthropic'e gönderilir — onay vermelisiniz."
        )

    eff_model_id = model or cfg.get("varsayilan_model") or ayarlar.MODEL_SONNET
    model_kisa = _model_alias(eff_model_id)
    klinik_iste = bool(cfg.get("klinik_yorum_iste", True))
    timeout_sn = int(cfg.get("subprocess_timeout_sn") or VARSAYILAN_TIMEOUT_SN)

    full = _full_prompt_olustur(paket, klinik_yorum_iste=klinik_iste)

    recete_no = ((paket.get("recete") or {}).get("recete_no") or "")
    ilac_adi = (((paket.get("recete") or {}).get("ilac") or {}).get("urun_adi") or "")
    hasta_tc_hash = ((paket.get("hasta") or {}).get("tc_hash") or "")
    sut_madde = ""
    if paket.get("rapor"):
        sut_madde = str((paket["rapor"]).get("rapor_kodu") or "")

    istat = CagriIstatistik(model=f"claude-code:{model_kisa}")
    parse_sonuc = sonuc_parser.AISonuc(sonuc=sonuc_parser.SONUC_HATA)
    cevap_text = ""
    hata = ""

    try:
        sub = subprocess_cagir(full, model=model_kisa, timeout=timeout_sn)
        cevap_text = sub.result_text
        istat.input_tokens = sub.input_tokens
        istat.output_tokens = sub.output_tokens
        istat.cached_input_tokens = sub.cache_read_tokens
        istat.cache_write_tokens = sub.cache_creation_tokens
        istat.latency_ms = sub.duration_ms
        # Max planda total_cost_usd metric — gerçek fatura yok ama tracking için al
        istat.maliyet_usd = sub.total_cost_usd
        parse_sonuc = sonuc_parser.parse(cevap_text)
    except (ClaudeCodeYok, SubprocessHata) as e:
        hata = f"{type(e).__name__}: {e}"
        parse_sonuc.hata = hata
        logger.warning("Subprocess kontrol hatası: %s", hata)
    except Exception as e:
        hata = f"{type(e).__name__}: {e}"
        parse_sonuc.hata = hata
        logger.exception("Subprocess beklenmedik hata")

    if log_kaydet:
        try:
            ai_log_db.cagri_kaydet(
                ri_id=ri_id,
                hasta_tc=hasta_tc_hash,
                recete_no=recete_no,
                ilac_adi=ilac_adi,
                sut_madde=sut_madde,
                model=istat.model,
                input_tokens=istat.input_tokens,
                output_tokens=istat.output_tokens,
                cached_input_tokens=istat.cached_input_tokens,
                cache_write_tokens=istat.cache_write_tokens,
                maliyet_usd=istat.maliyet_usd,
                latency_ms=istat.latency_ms,
                sonuc_etiketi=parse_sonuc.sonuc,
                guven_skoru=parse_sonuc.guven_skoru,
                cevap_text=cevap_text,
                hata=hata or parse_sonuc.hata,
            )
        except Exception as e_log:
            logger.warning("AI log kaydı atlandı: %s", e_log)

    if hata and parse_sonuc.sonuc == sonuc_parser.SONUC_HATA:
        raise AIIstemciHata(hata)

    return parse_sonuc, istat


def baglanti_test_et(model: Optional[str] = None) -> tuple[bool, str]:
    """Subprocess backend için bağlantı testi: kısa bir ping prompt."""
    ok, msg = saglik_kontrolu()
    if not ok:
        return False, msg
    try:
        sub = subprocess_cagir(
            "Sadece şu kelimeyi yaz: OK",
            model=_model_alias(model) if model else None,
            timeout=60,
        )
        if "OK" in (sub.result_text or "").upper():
            return True, (
                f"Subprocess OK ({sub.duration_ms}ms, "
                f"in/out={sub.input_tokens}/{sub.output_tokens}, "
                f"cost_metric=${sub.total_cost_usd:.4f})"
            )
        return False, f"Subprocess çalıştı ama beklenmedik cevap: {sub.result_text[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
