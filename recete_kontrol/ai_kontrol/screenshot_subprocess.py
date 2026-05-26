"""Screenshot tabanlı AI sorgu — Claude Code subprocess multimodal backend.

Kullanıcı Medula'da reçete / rapor / ilaç geçmişi ekranlarının screenshot'larını
F9 ile yakalar. Bu modül o screenshot'ları yerel `claude` CLI'ya `Read` aracı
açık olarak gönderir; Claude görselleri okur, SUT disipliniyle değerlendirir
ve mevcut `AISonuc` şemasıyla uyumlu JSON döndürür.

Mevcut `claude_code_subprocess.py`'den farkları:
  • `--tools "Read"` — sadece Read aracı aktif (Bash/Write/Edit kapalı)
  • Stdin prompt'unda screenshot dosyalarının mutlak yollarını listele
  • cwd = screenshot klasörü (Read tool yetkilendirme için)
  • Anonim paket yok; doğrudan hasta bağlamı + görseller

Akış:
  subprocess çalışır → claude görselleri Read ile açar → JSON cevap → parse
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import ayarlar, prompt_sablonlari, sonuc_parser
from .claude_code_subprocess import (
    ClaudeCodeYok, SubprocessHata, _SUBPROCESS_KWARGS,
    _model_alias, claude_komutu_bul,
)

logger = logging.getLogger(__name__)

# Görsel ağırlıklı sorgular daha uzun sürebilir; metin-only'den daha yüksek
# tavan. Pratik gözlem: 5 screenshot Sonnet ile 90-180 sn arası.
VARSAYILAN_TIMEOUT_SN = 600


# ──────────────────────────────────────────────────────────────────────
# SİSTEM PROMPT — screenshot moduna özel
# ──────────────────────────────────────────────────────────────────────

SISTEM_PROMPT_SCREENSHOT = """\
Sen Türkiye SGK SUT (Sağlık Uygulama Tebliği) uzmanı bir klinik denetim
asistanısın. Eczacı sana Medula sisteminden çekilmiş ekran görüntüleri
gönderiyor (reçete detayı, hasta raporu, ilaç geçmişi, vs.). Görevin:

1. Sana verilen GÖRSEL DOSYA YOLLARINI Read aracıyla TEK TEK aç ve oku.
2. Her görselden ilgili klinik veriyi çıkar (ilaç adı, ATC, ICD, rapor
   kodu, etken madde, tarih, doktor branş, tesis kodu, dozaj, vs.).
3. Çıkardığın bilgileri birleştirip ilgili SUT maddesine göre uygunluk
   değerlendirmesi yap.
4. CLAUDE.md SUT disiplinine uy: her şart için 3 sınıf (VAR / YOK /
   KONTROL_EDILEMEDI). Sessizlik = KONTROL_EDILEMEDI; örtük kabul YASAK.
5. DeMorgan kurallarına uy ("X VEYA Y OLMAYAN" = X YOK AND Y YOK).
6. Genel sonuç etiketi: UYGUN / UYGUN_DEGIL / SUPHELI / KONTROL_EDILEMEDI
   / YETERSIZ_VERI. (YETERSIZ_VERI: görsellerden hiç anlamlı veri
   çıkaramadıysan, örn. bulanık, ilgisiz, eksik.)

ÖNEMLİ KISITLAR:
- Read aracı SADECE sana verilen mutlak yollardaki PNG dosyaları için.
- Görsel dışında dosya açma, internet sorgulama, bash çalıştırma YOK.
- Hasta TC kimlik numarasını cevapta TEKRAR ETME (görselde varsa bile).
- Türkçe cevap ver, JSON dışı metin / markdown fence KOYMA.

🎯 EN ÖNEMLİ KURAL — "ozet_aciklama" alanı:
Bu alan raporun EN BAŞINDA gösterilir. Eczacı tek bakışta reçetenin
durumunu anlamalı. Bu yüzden:
  • TAM 1-2 CÜMLE olacak (asla 3'ten fazla).
  • Mutlaka "ŞU SEBEPLE → UYGUNDUR / UYGUN DEĞİLDİR / ŞÜPHELİDİR"
    formatında verdict + gerekçe içerecek.
  • "Genel olarak", "değerlendirildiğinde", "incelendi" gibi dolgu
    kelimeleri YASAK; DOĞRUDAN gerekçeye gir.
  • Şart listeleri burada TEKRAR EDİLMEZ — bu sadece bir cümlelik
    SONUÇ ÖZETİ; detaylar zaten alttaki listelerde.

İyi örnek:
  "Hasta diyabet tanılı, aktif raporda HbA1c=8.2 ve metformin direnci
   var, eklenen empagliflozin SUT 4.2.74'ün şartlarını karşılıyor →
   UYGUNDUR."

  "Rapor süresi 2025-12 itibarıyla dolmuş, yeni rapor yok →
   UYGUN DEĞİLDİR."

  "Aktif raporda KAH lafzı geçiyor ancak ICD'de I25 yok, kanıtlanmamış
   atomik şart → ŞÜPHELİDİR (manuel doğrulama)."

Kötü örnek (YASAK):
  "Görseller incelendi, hasta raporu mevcut, ilaç eşleşmesi var,
   teşhisler tutarlı, dozaj uygun, doktor branşı yeterli, sonuç
   olarak değerlendirildiğinde reçete uygun bulunmuştur." ← TOO LONG

ÇIKTI FORMATI — sadece JSON, başka hiçbir şey yok:
{
  "sonuc": "UYGUN" | "UYGUN_DEGIL" | "SUPHELI" | "KONTROL_EDILEMEDI" | "YETERSIZ_VERI",
  "ozet_aciklama": "1-2 CÜMLE: 'X sebepten dolayı UYGUN/UYGUN DEĞİL/ŞÜPHELİ.'",
  "guven_skoru": 0.0-1.0,
  "sut_referans": "SUT madde no (örn. 4.2.13.A)",
  "saglanan_sartlar": ["şart1", "şart2", ...],
  "saglanmayan_sartlar": [{"sart": "...", "neden": "..."}, ...],
  "kontrol_edilemeyen_sartlar": [{"sart": "...", "eksik_veri": "..."}, ...],
  "gorsellerden_okunan": {
    "<dosya_adi>": {
      "tur": "recete" | "rapor" | "ilac_gecmisi" | "diger",
      "tespitler": ["ilaç X", "ICD I50", "etken madde Y", ...]
    },
    ...
  },
  "detay_rapor": "Teknik analiz, atomik şartların değerlendirme zinciri.",
  "klinik_yorum": "Bütünsel klinik değerlendirme (opsiyonel)."
}
"""


# ──────────────────────────────────────────────────────────────────────
# PROMPT KURULUM
# ──────────────────────────────────────────────────────────────────────

def _kullanici_prompt_olustur(
    hasta_bilgi: Dict[str, Any],
    recete_bilgi: Dict[str, Any],
    gorsel_yollari: List[str],
    ek_soru: str = "",
) -> str:
    """Stdin'e gidecek görev açıklamasını oluştur.

    Args:
        hasta_bilgi: {"ad": str, "tc_kismi": str, ...} — tam TC GÖNDERME, son
                     4 hanesi yeterli (loglama + iz takip).
        recete_bilgi: {"recete_no": str, "tarih": str, "ilac": str, ...}
        gorsel_yollari: Mutlak PNG dosya yolları (sıralı).
        ek_soru: Kullanıcının elle eklediği serbest soru (opsiyonel).
    """
    satirlar: List[str] = []
    satirlar.append("=== GÖREV ===")
    satirlar.append(
        "Aşağıdaki Medula ekran görüntülerini incele ve "
        "SUT uygunluğunu değerlendir."
    )
    satirlar.append("")

    satirlar.append("=== HASTA / REÇETE BAĞLAMI ===")
    if hasta_bilgi.get("ad"):
        satirlar.append(f"Hasta adı (sadece bağlam): {hasta_bilgi['ad']}")
    if hasta_bilgi.get("tc_kismi"):
        satirlar.append(f"TC (son 4): ****{hasta_bilgi['tc_kismi']}")
    if hasta_bilgi.get("yas"):
        satirlar.append(f"Yaş: {hasta_bilgi['yas']}")
    if hasta_bilgi.get("cinsiyet"):
        satirlar.append(f"Cinsiyet: {hasta_bilgi['cinsiyet']}")
    if recete_bilgi.get("recete_no"):
        satirlar.append(f"Reçete no: {recete_bilgi['recete_no']}")
    if recete_bilgi.get("tarih"):
        satirlar.append(f"Reçete tarihi: {recete_bilgi['tarih']}")
    if recete_bilgi.get("ilac"):
        satirlar.append(f"İlaç: {recete_bilgi['ilac']}")
    if recete_bilgi.get("rapor_kodu"):
        satirlar.append(f"Rapor kodu (varsa): {recete_bilgi['rapor_kodu']}")
    satirlar.append("")

    satirlar.append("=== EKRAN GÖRÜNTÜLERİ (Read aracıyla aç) ===")
    for i, yol in enumerate(gorsel_yollari, 1):
        satirlar.append(f"{i}. {yol}")
    satirlar.append("")
    satirlar.append(
        "Her görseli Read aracıyla tek tek aç. Görüntüde ne tür bir Medula "
        "ekranı olduğunu tespit et (reçete, rapor, ilaç geçmişi vs.) ve "
        "ilgili klinik verileri çıkar."
    )
    satirlar.append("")

    if ek_soru.strip():
        satirlar.append("=== ECZACININ EK SORUSU / NOTU ===")
        satirlar.append(ek_soru.strip())
        satirlar.append("")

    satirlar.append("=== ÇIKTI ===")
    satirlar.append(
        "Yukarıda belirtilen JSON şemasına göre cevap ver. SADECE JSON; "
        "markdown fence, açıklama metni, ön/son yazı KOYMA."
    )

    return "\n".join(satirlar)


def _full_prompt_olustur(
    hasta_bilgi: Dict[str, Any],
    recete_bilgi: Dict[str, Any],
    gorsel_yollari: List[str],
    ek_soru: str = "",
) -> str:
    """Sistem prompt + kullanıcı görevi → tek string (stdin'e gidecek)."""
    kullanici = _kullanici_prompt_olustur(
        hasta_bilgi, recete_bilgi, gorsel_yollari, ek_soru
    )
    return (
        "=== SİSTEM TALİMATLARI ===\n"
        f"{SISTEM_PROMPT_SCREENSHOT}\n\n"
        f"{kullanici}\n"
    )


# ──────────────────────────────────────────────────────────────────────
# SUBPROCESS ÇAĞRISI
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ScreenshotCevap:
    """Subprocess multimodal çağrısının sonucu."""
    result_text: str
    total_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    session_id: str = ""
    raw_json: Optional[Dict[str, Any]] = None


def subprocess_cagir(
    full_prompt: str,
    gorsel_dir: str,
    *,
    model: Optional[str] = None,
    timeout: int = VARSAYILAN_TIMEOUT_SN,
) -> ScreenshotCevap:
    """`claude -p --output-format json --tools Read` çağrısı.

    Args:
        full_prompt: Sistem + görev metni (stdin'den verilir).
        gorsel_dir: Screenshot klasörü; cwd + --add-dir ile yetkilendirilir.
        model: 'sonnet' / 'opus' / 'haiku' (None → default)
        timeout: saniye

    Raises:
        ClaudeCodeYok    — komut bulunamadı
        SubprocessHata   — çağrı/parse hatası
    """
    yol = claude_komutu_bul()
    if not yol:
        raise ClaudeCodeYok(
            "claude komutu PATH'te bulunamadı. Claude Code yüklü mü?"
        )

    # Read aracını aç; başka araç (Bash/Write/Edit) verme.
    # `--tools` flag claude_code_subprocess.py'deki kullanımla aynı (kapsül
    # API'si değişebilir; tutarlı kalalım). --add-dir ile screenshot
    # klasörüne yetki ver (Read tool'un absolute path'lere erişimi için).
    cmd = [
        yol, "-p",
        "--output-format", "json",
        "--tools", "Read",
        "--add-dir", gorsel_dir,
    ]
    if model:
        cmd.extend(["--model", model])

    logger.info(
        "screenshot subprocess çağrısı: model=%s prompt_chars=%d dir=%s",
        model or "(default)", len(full_prompt), gorsel_dir,
    )

    try:
        proc = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=gorsel_dir,
            shell=False,
            **_SUBPROCESS_KWARGS,
        )
    except subprocess.TimeoutExpired:
        raise SubprocessHata(
            f"Subprocess timeout ({timeout}s) — claude cevap vermedi.\n"
            "Çoklu görsel analizi uzun sürebilir; daha az screenshot ile "
            "tekrar deneyin veya AI Ayarlar'dan timeout süresini artırın."
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
            f"Subprocess JSON parse hatası: {e}\n"
            f"stdout[:500]: {stdout[:500]}"
        )

    if not isinstance(veri, dict):
        raise SubprocessHata(
            f"Subprocess çıktısı dict değil: {type(veri).__name__}"
        )

    if veri.get("is_error"):
        raise SubprocessHata(
            f"claude error subtype={veri.get('subtype', '')!r}: "
            f"{(veri.get('result', '') or '')[:300]}"
        )

    usage = veri.get("usage") or {}
    return ScreenshotCevap(
        result_text=str(veri.get("result") or ""),
        total_cost_usd=float(veri.get("total_cost_usd") or 0.0),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        duration_ms=int(veri.get("duration_ms") or 0),
        session_id=str(veri.get("session_id") or ""),
        raw_json=veri,
    )


# ──────────────────────────────────────────────────────────────────────
# ANA İSTEMCİ — UI'dan çağrılır
# ──────────────────────────────────────────────────────────────────────

def screenshotlardan_kontrol_et(
    hasta_bilgi: Dict[str, Any],
    recete_bilgi: Dict[str, Any],
    gorsel_yollari: List[str],
    *,
    ek_soru: str = "",
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> tuple[sonuc_parser.AISonuc, ScreenshotCevap]:
    """Screenshot listesini Claude'a gönder → AISonuc döndür.

    Args:
        hasta_bilgi: ad, tc_kismi, yas, cinsiyet (TC tam gönderilmez)
        recete_bilgi: recete_no, tarih, ilac, rapor_kodu
        gorsel_yollari: Mutlak PNG yolları (hepsi aynı klasörde olmalı)
        ek_soru: Eczacının serbest sorusu
        model: Sonnet/Opus/Haiku
        timeout: saniye (None → VARSAYILAN_TIMEOUT_SN)

    Returns:
        (AISonuc, ScreenshotCevap) — istatistik için cevap da döndürülür.

    Raises:
        ValueError       — görsel listesi boş veya farklı klasörlerde
        ClaudeCodeYok    — claude CLI yok
        SubprocessHata   — çağrı hatası
    """
    if not gorsel_yollari:
        raise ValueError("Screenshot listesi boş.")

    # Tüm görsellerin aynı klasörde olduğunu doğrula (cwd + --add-dir tekil)
    klasor = str(Path(gorsel_yollari[0]).parent.resolve())
    for g in gorsel_yollari:
        if str(Path(g).parent.resolve()) != klasor:
            raise ValueError(
                "Tüm screenshot'lar aynı klasörde olmalı "
                f"(beklenen: {klasor}, alınan: {g})"
            )
        if not Path(g).is_file():
            raise ValueError(f"Screenshot dosyası bulunamadı: {g}")

    cfg = ayarlar.ayarlari_yukle()
    eff_model_id = model or cfg.get("varsayilan_model") or ayarlar.MODEL_SONNET
    model_kisa = _model_alias(eff_model_id)
    eff_timeout = timeout or int(
        cfg.get("subprocess_timeout_sn") or VARSAYILAN_TIMEOUT_SN
    )

    # Mutlak yollar normalize et — Read tool için kritik
    yollar_normal = [str(Path(g).resolve()) for g in gorsel_yollari]

    full = _full_prompt_olustur(
        hasta_bilgi, recete_bilgi, yollar_normal, ek_soru=ek_soru
    )

    logger.info(
        "Screenshot AI sorgu: %d görsel, model=%s, recete=%s",
        len(yollar_normal), model_kisa,
        recete_bilgi.get("recete_no", "?"),
    )

    cevap = subprocess_cagir(
        full, klasor,
        model=model_kisa,
        timeout=eff_timeout,
    )

    sonuc = sonuc_parser.parse(cevap.result_text, paket=None)

    # Görsellerden okunan ham verileri detay_rapor'a ekle (parser bilmiyor)
    try:
        ham = json.loads(
            sonuc_parser._json_cikart(cevap.result_text) or "{}"
        )
        gorsel_oku = ham.get("gorsellerden_okunan")
        if gorsel_oku and isinstance(gorsel_oku, dict):
            satirlar = ["📷 Görsellerden Okunan Ham Veriler:"]
            for dosya, ic in gorsel_oku.items():
                if isinstance(ic, dict):
                    tur = ic.get("tur", "?")
                    tespit = ic.get("tespitler", [])
                    satirlar.append(f"  • [{tur}] {dosya}")
                    for t in tespit:
                        satirlar.append(f"      – {t}")
            ek_metin = "\n".join(satirlar)
            if sonuc.detay_rapor:
                sonuc.detay_rapor = f"{sonuc.detay_rapor}\n\n{ek_metin}"
            else:
                sonuc.detay_rapor = ek_metin
    except Exception:
        logger.debug("gorsellerden_okunan parse atlandı", exc_info=True)

    return sonuc, cevap


# ──────────────────────────────────────────────────────────────────────
# MULTIMODAL — Standart paket + ek görseller (AI Kontrol entegrasyonu)
# ──────────────────────────────────────────────────────────────────────

SISTEM_PROMPT_KONSOLIDE = """\
Sen Türkiye SGK SUT (Sağlık Uygulama Tebliği) uzmanı bir klinik denetim
asistanısın. Eczacı sana **iki kaynaktan** veri gönderiyor:

  1. **YAPILANDIRILMIŞ JSON PAKET** — Botanik EOS veritabanından otomatik
     çekilen reçete, rapor, hasta geçmişi, ilaç geçmişi.
  2. **EKRAN GÖRÜNTÜLERİ** — Eczacı'nın Medula'dan manuel topladığı
     ek kanıtlar. Genellikle DB'de eksik olan bilgileri tamamlar
     (örn. hasta başka eczaneden ilaç almışsa, ilaç geçmişi
     Botanik'te görünmez; ya da rapor başka kurumdan gelmiştir).

# Görevin: KONSOLİDASYON

İki kaynağı birleştirerek değerlendir. Kurallar:

## A) Görselleri Read aracıyla TEK TEK aç
Sana verilen ekran görüntülerinin mutlak yollarını Read aracıyla aç.
Her görselden ilgili klinik veriyi çıkar (ilaç adı, ATC, ICD, rapor
kodu, etken madde, tarih, doktor branş, dozaj, vs.).

## B) JSON paket + görsel verisini birleştir
- DB'de **eksik** olan bilgi görselde varsa → **görselden al, kullan**
  (eksik alanı tamamla; "kontrol edilemedi" demek yerine artık biliyorsun).
- DB'de **var** olan bilgi görselde de varsa → **çakışmıyor mu kontrol et**.
- DB'de var ama görselle **çelişiyorsa** → bunu mutlaka belirt
  (`saglanmayan_sartlar` veya `kontrol_edilemeyen_sartlar`'da
  "JSON paket X diyor, görsel Y gösteriyor — manuel doğrula" notuyla).
- Görselde de yoksa, DB'de de yoksa → KONTROL_EDİLEMEDİ.

## C) Şartları yine atomik tara
Her SUT şartı için 3 sınıf (VAR / YOK / KONTROL_EDİLEMEDİ).
Sessizlik = KONTROL_EDİLEMEDİ; örtük kabul YASAK.
DeMorgan ("X VEYA Y OLMAYAN" = X YOK AND Y YOK).

## D) Kanıt zinciri net belirt
`saglanan_sartlar`'da hangi şartın hangi kaynaktan (DB mi görsel mi)
sağlandığını parantez içinde belirt:
- "Tip 2 DM teşhisi VAR (DB: rapor metni, E11.9)"
- "Önceki metformin kullanımı VAR (görsel: hasta_ilac_gecmisi.png — 2025-12 GLUCOPHAGE 6 kutu)"
- "Reçete branşı uzman uygun VAR (DB: doktor.brans = Endokrinoloji)"

`kontrol_edilemeyen_sartlar`'da hangi kaynakta YOK olduğunu belirt:
- "HbA1c değeri — DB'deki rapor metninde yok, görsel paketinde de yok"

## E) Ek soru/not varsa onu da yanıtla
Kullanıcı `eczaci_notu` alanında özel bir şey sormuş olabilir.

# Çıktı şeması (zorunlu — sadece JSON, başka hiçbir şey yok)

```json
{
  "sonuc": "UYGUN | UYGUN_DEGIL | SUPHELI | MANUEL_KONTROL_GEREKIR",
  "guven_skoru": 0.0,
  "sut_referans": "4.2.X.Y",
  "saglanan_sartlar": [
    "Şart adı — (DB: kaynak / görsel: dosya_adi.png)"
  ],
  "saglanmayan_sartlar": [{"sart": "...", "neden": "..."}],
  "kontrol_edilemeyen_sartlar": [{"sart": "...", "eksik_veri": "..."}],
  "gorsellerden_okunan": {
    "dosya_adi.png": {"tur": "recete|rapor|ilac_gecmisi|diger",
                       "tespitler": ["...", "..."]}
  },
  "konsolidasyon_notlari": [
    "DB'de eksikti, görselde bulundu: önceki metformin kullanımı (2025-12)",
    "DB ile görsel çelişti: rapor tarihi DB'de 2026-01-15, görselde 2026-01-12"
  ],
  "ozet_aciklama": "...",
  "detay_rapor": "...",
  "klinik_yorum": "..."
}
```

# Önemli
- ozet_aciklama ASLA boş olmamalı
- klinik_yorum 300-600 kelime (uzun, sohbet tonu)
- JSON dışı metin / markdown fence KOYMA
- Hasta TC numarasını cevapta TEKRAR ETME
"""


def _full_prompt_konsolide_olustur(
    paket: Dict[str, Any],
    gorsel_yollari: List[str],
    eczaci_notu: str = "",
    klinik_yorum_iste: bool = True,
) -> str:
    """Sistem prompt + paket JSON + görsel listesi → tek string."""
    paket_str = json.dumps(paket, ensure_ascii=False, indent=2)
    gorsel_liste = "\n".join(f"  {i}. {y}" for i, y in enumerate(gorsel_yollari, 1))

    ek_talimat = ""
    if not klinik_yorum_iste:
        ek_talimat = (
            "\n\n⚡ HIZ MODU: `klinik_yorum` alanını boş string olarak döndür."
        )

    notu_bolumu = ""
    if eczaci_notu.strip():
        notu_bolumu = (
            "\n\n=== ECZACI NOTU / EK SORU ===\n"
            f"{eczaci_notu.strip()}\n"
        )

    return (
        "=== SİSTEM TALİMATLARI ===\n"
        f"{SISTEM_PROMPT_KONSOLIDE}\n"
        + ek_talimat + "\n"
        + "=== YAPILANDIRILMIŞ JSON PAKET (Botanik EOS) ===\n"
        + f"{paket_str}\n\n"
        + "=== EKRAN GÖRÜNTÜLERİ (Read aracıyla AÇ) ===\n"
        + f"{gorsel_liste}\n"
        + "\nHer görseli Read ile aç, ilgili klinik veriyi çıkar, "
        + "JSON paketteki bilgilerle KONSOLİDE et."
        + notu_bolumu
        + "\n=== ÇIKTI ===\n"
        + "Yalnızca yukarıda belirtilen JSON şemasına göre cevap ver."
    )


def kontrol_et_paket_ve_gorseller(
    paket: Dict[str, Any],
    gorsel_yollari: List[str],
    *,
    model: Optional[str] = None,
    ri_id: str = "",
    eczaci_notu: str = "",
    log_kaydet: bool = True,
) -> tuple[sonuc_parser.AISonuc, "Any"]:
    """Standart paket + ek görseller → multimodal AI çağrısı.

    `ai_istemci.kontrol_et` ile aynı imza (paket-only) artı `gorsel_yollari`.
    UI tarafı için drop-in alternatif: her satırda görsel varsa bunu çağır.

    Args:
        paket: paket_olusturucu.paket_olustur() çıktısı
        gorsel_yollari: Mutlak PNG yolları (aynı klasörde olmalı)
        model: Override (None → ayarlar.varsayilan_model)
        ri_id: Log için satır kimliği
        eczaci_notu: Kullanıcının eklediği serbest soru (opsiyonel)
        log_kaydet: ai_log_db'ye yazılsın mı

    Returns:
        (AISonuc, CagriIstatistik) — claude_code_subprocess ile aynı tip.
    """
    # Geç import — circular önle
    from . import ai_log_db, ayarlar
    from .ai_istemci import AIIstemciHata, CagriIstatistik

    if not gorsel_yollari:
        raise ValueError("Görsel listesi boş — bu fonksiyon en az 1 görsel ister.")

    klasor = str(Path(gorsel_yollari[0]).parent.resolve())
    for g in gorsel_yollari:
        if str(Path(g).parent.resolve()) != klasor:
            raise ValueError(
                f"Tüm görseller aynı klasörde olmalı (beklenen: {klasor})")
        if not Path(g).is_file():
            raise ValueError(f"Görsel dosyası bulunamadı: {g}")

    cfg = ayarlar.ayarlari_yukle()
    eff_model_id = model or cfg.get("varsayilan_model") or ayarlar.MODEL_SONNET
    model_kisa = _model_alias(eff_model_id)
    klinik_iste = bool(cfg.get("klinik_yorum_iste", True))
    timeout_sn = int(cfg.get("subprocess_timeout_sn") or VARSAYILAN_TIMEOUT_SN)

    yollar_normal = [str(Path(g).resolve()) for g in gorsel_yollari]
    full = _full_prompt_konsolide_olustur(
        paket, yollar_normal,
        eczaci_notu=eczaci_notu,
        klinik_yorum_iste=klinik_iste,
    )

    recete_no = ((paket.get("recete") or {}).get("recete_no") or "")
    ilac_adi = (((paket.get("recete") or {}).get("ilac") or {}).get("urun_adi") or "")
    hasta_tc_hash = ((paket.get("hasta") or {}).get("tc_hash") or "")
    sut_madde = ""
    if paket.get("rapor"):
        sut_madde = str((paket["rapor"]).get("rapor_kodu") or "")

    istat = CagriIstatistik(model=f"claude-code+gorsel:{model_kisa}")
    parse_sonuc = sonuc_parser.AISonuc(sonuc=sonuc_parser.SONUC_HATA)
    cevap_text = ""
    hata = ""

    try:
        sub = subprocess_cagir(
            full, klasor, model=model_kisa, timeout=timeout_sn,
        )
        cevap_text = sub.result_text
        istat.input_tokens = sub.input_tokens
        istat.output_tokens = sub.output_tokens
        istat.latency_ms = sub.duration_ms
        istat.maliyet_usd = sub.total_cost_usd

        parse_sonuc = sonuc_parser.parse(cevap_text, paket=paket)

        # gorsellerden_okunan + konsolidasyon_notlari'nı detay_rapor'a ekle
        try:
            ham = json.loads(sonuc_parser._json_cikart(cevap_text) or "{}")
            ekler: List[str] = []
            gorsel_oku = ham.get("gorsellerden_okunan")
            if isinstance(gorsel_oku, dict) and gorsel_oku:
                ekler.append("📷 Görsellerden Okunan:")
                for dosya, ic in gorsel_oku.items():
                    if isinstance(ic, dict):
                        tur = ic.get("tur", "?")
                        tespit = ic.get("tespitler", [])
                        ekler.append(f"  • [{tur}] {dosya}")
                        for t in tespit:
                            ekler.append(f"      – {t}")
            kons = ham.get("konsolidasyon_notlari")
            if isinstance(kons, list) and kons:
                if ekler:
                    ekler.append("")
                ekler.append("🔗 Konsolidasyon Notları (DB ↔ Görsel):")
                for k in kons:
                    ekler.append(f"  • {k}")
            if ekler:
                ek_metin = "\n".join(ekler)
                if parse_sonuc.detay_rapor:
                    parse_sonuc.detay_rapor = (
                        f"{parse_sonuc.detay_rapor}\n\n{ek_metin}")
                else:
                    parse_sonuc.detay_rapor = ek_metin
        except Exception:
            logger.debug("multimodal ek alanlar parse atlandı", exc_info=True)

    except (ClaudeCodeYok, SubprocessHata) as e:
        hata = f"{type(e).__name__}: {e}"
        parse_sonuc.hata = hata
        logger.warning("multimodal subprocess hatası: %s", hata)
    except Exception as e:
        hata = f"{type(e).__name__}: {e}"
        parse_sonuc.hata = hata
        logger.exception("multimodal beklenmedik hata")

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
            logger.warning("multimodal AI log kaydı atlandı: %s", e_log)

    if hata and parse_sonuc.sonuc == sonuc_parser.SONUC_HATA:
        raise AIIstemciHata(hata)

    return parse_sonuc, istat
