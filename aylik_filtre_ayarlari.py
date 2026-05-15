"""
Aylık İnceleme — Gelişmiş Filtre Ayarları

İki katmanlı filtre sistemi:

1) İÇERİK FİLTRESİ (4 toggle):
   Bir satır en az birinden geçerse getirilir:
   - Renkli reçete (Kırmızı/Yeşil/Mor)
   - İlaç mesajı var
   - Uyarı kodu var
   - Rapor kodu var

2) LİSTE BAZLI FİLTRELER (4 liste, her biri whitelist/blacklist mod ile):
   - İlaç adları
   - Etken maddeler
   - ATC grupları
   - Farmasötik formlar

   Mod seçenekleri:
   - 'yok'        → liste devre dışı
   - 'getir'      → SADECE bu listedekiler gelsin (whitelist)
   - 'getirme'    → bu listedekiler GELMESİN (blacklist)

GÜVENLİK: Sadece SELECT — Botanik EOS'ta hiçbir veri değişmez.
"""
import json
import os
import logging

logger = logging.getLogger(__name__)


# Ayar JSON dosyası
AYAR_DOSYASI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "aylik_filtre_ayarlari.json"
)


# Liste tipleri
# NOT: "kurum", "sgk" ve "doktor" sekmelerindeki içerir/içermez kuralları
# "Boş Satırları Gizle" toggle'ından BAĞIMSIZ her zaman uygulanır
# (eski Dışlamalar fonksiyonunun yerine geçer). Diğer tipler toggle'a tabidir.
LISTE_TIPLERI = ("ilac", "etken", "atc", "farma", "tesis", "esdeger",
                  "kurum", "sgk", "doktor", "brans")
LISTE_ETIKETLERI = {
    "ilac":     "İlaç Adı",
    "etken":    "Etken Madde",
    "atc":      "ATC Grubu",
    "farma":    "Farmasötik Form",
    "tesis":    "Tesis (Hastane Kodu / Adı)",
    "esdeger":  "Eşdeğer Grubu",
    "kurum":    "🚫 Kurum (Dışlamalar)",
    "sgk":      "🔢 SGK İşlem No",
    "doktor":   "👨‍⚕️ Doktor (Hekim)",
    "brans":    "🏥 Branş (Hekim Uzmanlık)",
}


VARSAYILAN = {
    # ── İçerik filtresi (her biri "getir mi?") ──
    "renkli_getir": True,       # Kırmızı/Yeşil/Mor reçeteler
    "mesaj_getir":  True,       # Mesajı olan ilaçlar
    "uyari_getir":  True,       # Uyarı kodu olanlar
    "rapor_getir":  True,       # Rapor kodu olanlar

    # ── SGK reçetesi olmayanları dışla (default AÇIK) ──
    # RxSgkIslemNo NULL veya boş olan reçeteler = SGK olmayan (apra vb.)
    # Toggle AÇIKsa bu reçeteler hiç gelmez. Kapatılırsa tümü gelir.
    "sgk_bos_disla": True,

    # ── Liste bazlı filtreler ──
    # Her tip için liste: [{"deger": "...", "mod": "icerir"|"icermez"}, ...]
    # mod="icerir"  → kural geçerli ise satır gelir (whitelist davranışı)
    # mod="icermez" → kural geçerli ise satır gelmez (blacklist davranışı)
    # Boş liste → o tip için kural yok
    "ilac":     [],
    "etken":    [],
    "atc":      [],
    "farma":    [],
    "tesis":    [],
    "esdeger":  [],
    "kurum":    [],
    "sgk":      [],   # RxSgkIslemNo pattern dışlama (örn. "M0000*" prefix)
    "doktor":   [],   # DoktorAdiSoyadi pattern dışlama (örn. kronik hekim)
    "brans":    [],   # BransAdi pattern dışlama (örn. "AILE HEKIMI", "ACIL")
}


def _eski_format_mi(cfg) -> bool:
    """Eski format: {'mod': 'yok|getir|getirme', 'ogeler': [...]}"""
    return isinstance(cfg, dict) and "mod" in cfg and "ogeler" in cfg


def _eski_yeniye_donustur(cfg) -> list:
    """Eski format → yeni format (per-item içerir/içermez)."""
    if not _eski_format_mi(cfg):
        return []
    mod = cfg.get("mod", "yok")
    ogeler = cfg.get("ogeler", []) or []
    if mod == "yok" or not ogeler:
        return []
    yeni_mod = "icerir" if mod == "getir" else "icermez"
    return [{"deger": str(s).strip(), "mod": yeni_mod}
            for s in ogeler if str(s).strip()]


def ayarlari_yukle() -> dict:
    """JSON'dan oku, eksikleri varsayılanla doldur. Eski formatı yeniye
    çevirir."""
    sonuc = {k: (list(v) if isinstance(v, list) else v)
              for k, v in VARSAYILAN.items()}
    if not os.path.exists(AYAR_DOSYASI):
        return sonuc
    try:
        with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
            ay = json.load(f)
    except Exception as e:
        logger.warning("Filtre ayarları okunamadı: %s", e)
        return sonuc

    # İçerik toggle'ları
    for k in ("renkli_getir", "mesaj_getir", "uyari_getir", "rapor_getir"):
        if k in ay:
            sonuc[k] = bool(ay[k])

    # SGK boş dışla toggle — JSON'da yoksa varsayılan AÇIK kalır
    if "sgk_bos_disla" in ay:
        sonuc["sgk_bos_disla"] = bool(ay["sgk_bos_disla"])

    # Liste bazlı filtreler — eski/yeni format desteği
    for tip in LISTE_TIPLERI:
        v = ay.get(tip)
        if isinstance(v, list):
            # Yeni format
            kurallar = []
            for item in v:
                if isinstance(item, dict):
                    deger = (item.get("deger") or "").strip()
                    mod = item.get("mod", "icerir")
                    if mod not in ("icerir", "icermez"):
                        mod = "icerir"
                    if deger:
                        kurallar.append({"deger": deger, "mod": mod})
                elif isinstance(item, str) and item.strip():
                    # Düz string listesi → tümü içerir kabul et
                    kurallar.append({"deger": item.strip(), "mod": "icerir"})
            sonuc[tip] = kurallar
        elif _eski_format_mi(v):
            sonuc[tip] = _eski_yeniye_donustur(v)
        else:
            sonuc[tip] = []

    # Eski dislama_ayarlari.json → "kurum" sekmesine icermez olarak migrate
    # et. Sadece JSON'da "kurum" anahtarı YOKSA (ilk kez) yapılır; sonraki
    # çağrılarda kullanıcının kurum sekmesindeki kararına dokunmaz.
    if "kurum" not in ay:
        try:
            _eski_dislama_dosyasi = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "dislama_ayarlari.json")
            if os.path.exists(_eski_dislama_dosyasi):
                with open(_eski_dislama_dosyasi, "r",
                          encoding="utf-8") as _f:
                    _eski = json.load(_f)
                _kd = _eski.get("kurum_dislama") or []
                _migrate = []
                for _it in _kd:
                    if not isinstance(_it, dict):
                        continue
                    _kid = _it.get("id")
                    _ad = (_it.get("ad") or "").strip()
                    if _kid is None:
                        continue
                    _deger = f"{int(_kid)} — {_ad}" if _ad else str(int(_kid))
                    _migrate.append({"deger": _deger, "mod": "icermez"})
                if _migrate:
                    sonuc["kurum"] = _migrate
                    # Kalıcı kaydet ki bir sonraki açılışta migrate
                    # tekrar tetiklenmesin.
                    ayarlari_kaydet(sonuc)
                    logger.info(
                        "Eski dislama_ayarlari.json → %d kurum kuralı "
                        "Filtre Ayarları > Kurum sekmesine taşındı.",
                        len(_migrate))
        except Exception as _e:
            logger.debug("Kurum dışlama migrasyonu skip edildi: %s", _e)

    return sonuc


def ayarlari_kaydet(ay: dict):
    """JSON'a yaz."""
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ay, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Filtre ayarları yazılamadı: %s", e)


def hicbir_icerik_secili_mi(ay: dict) -> bool:
    """4 içerik toggle'ından hiçbiri açık değilse True."""
    return not (ay.get("renkli_getir") or ay.get("mesaj_getir")
                or ay.get("uyari_getir") or ay.get("rapor_getir"))


def sql_icerik_kosullari(ay: dict, renkli_recete_idler: list) -> str:
    """İçerik filtresine göre SQL WHERE parçası üret.

    Args:
        ay: filtre ayarları dict
        renkli_recete_idler: ReceteRenk tablosundan Kırmızı/Yeşil/Mor ID'leri

    Returns:
        WHERE'e eklenecek koşul (parantezsiz, "AND" ile birleştirilmesi
        bekleyen) — boş string ise filtre yok demektir.
    """
    or_kosullar = []
    if ay.get("renkli_getir") and renkli_recete_idler:
        renkli_in = ",".join(str(int(i)) for i in renkli_recete_idler)
        or_kosullar.append(f"ra.RxReceteRenkId IN ({renkli_in})")
    if ay.get("mesaj_getir"):
        or_kosullar.append(
            "EXISTS ("
            "  SELECT 1 FROM UMTUrunMesaj umt"
            "  LEFT JOIN UMTMesaj m ON m.UMTMId = umt.UMTUMUMTMesajId"
            "  WHERE umt.UMTUMUrunId = ri.RIUrunId"
            "    AND m.UMTMMesaj IS NOT NULL"
            "    AND LEN(LTRIM(RTRIM(m.UMTMMesaj))) > 0"
            ")"
        )
    if ay.get("uyari_getir"):
        or_kosullar.append(
            "EXISTS ("
            "  SELECT 1 FROM ReceteTeshis rt"
            "  WHERE rt.RTRxId = ra.RxId"
            "    AND rt.RTTeshisKodu IS NOT NULL"
            "    AND LEN(LTRIM(RTRIM(rt.RTTeshisKodu))) > 0"
            "    AND (rt.RTUrunId IS NULL OR rt.RTUrunId = ri.RIUrunId)"
            ")"
        )
    if ay.get("rapor_getir"):
        or_kosullar.append(
            "(ri.RIRaporKodId IS NOT NULL AND ri.RIRaporKodId > 0)")

    if not or_kosullar:
        # 4 kriter de KAPALI → içerik filtresi devre dışı.
        # Eski davranış: "1 = 0" döndürüp tabloyu boşaltıyordu (kullanıcı
        # tüm toggle'ları kapatınca sessizce hiçbir satır görmüyordu).
        # Yeni davranış: boş string → SQL'de WHERE'e koşul EKLENMEZ →
        # liste filtreleri (varsa) ve diğer şartlar normal çalışır.
        return ""
    return "(" + " OR ".join(or_kosullar) + ")"


def _q(s: str) -> str:
    """SQL nvarchar literal — single-quote escape."""
    return "N'" + str(s).replace("'", "''").strip() + "'"


def _esit_kosul(kolon: str, deger: str) -> str:
    """Tam eşitlik (= operatörü). NULL-safe: ISNULL(x, '') = deger."""
    return f"ISNULL({kolon}, N'') = {_q(deger)}"


def _like_kosul(kolon: str, deger: str) -> str:
    """LIKE %deger% (case-insensitive). NULL-safe: ISNULL(x, '') üzerinden."""
    safe = str(deger).replace("'", "''").strip()
    return f"UPPER(ISNULL({kolon}, N'')) LIKE UPPER(N'%{safe}%')"


def _kategori_kosul(kurallar: list, kosul_fn) -> str:
    """Bir kategori için içerir/içermez kurallarını SQL'e çevir.

    İçerir kuralları OR ile birleşir (en az biri sağlansa yeter).
    İçermez kuralları AND NOT ile birleşir (hiçbiri eşleşmemeli).
    İkisi de varsa: (içerir OR ...) AND (NOT içermez1 AND NOT içermez2)

    NOT: kosul_fn'lerinin tümü NULL-safe (ISNULL ile sarılı) olmalı —
    aksi halde sütunda NULL olan satırlar (ör. UrunEsdegerId=NULL) tüm
    "icermez" kurallarından UNKNOWN üretip yanlışlıkla elenir.
    """
    if not kurallar:
        return ""
    icerir = [k for k in kurallar if k.get("mod") == "icerir"
              and k.get("deger")]
    icermez = [k for k in kurallar if k.get("mod") == "icermez"
               and k.get("deger")]
    parcalar = []
    if icerir:
        parcalar.append("(" + " OR ".join(kosul_fn(k["deger"])
                                            for k in icerir) + ")")
    if icermez:
        parcalar.append(" AND ".join("NOT " + kosul_fn(k["deger"])
                                       for k in icermez))
    return " AND ".join(parcalar)


def sql_liste_kosullari(ay: dict) -> str:
    """Liste bazlı filtrelerden SQL WHERE parçası üret. Her kategorideki
    kurallar içerir/içermez moduna göre birleşir; kategoriler arası VE.

    NOT: "kurum" tipi BURAYA dahil DEĞİLDİR — `sql_kurum_kosullari` ile
    toggle'dan bağımsız her zaman uygulanır (eski Dışlamalar davranışı).
    """
    parcalar = []

    # İlaç adı — tam eşitlik
    p = _kategori_kosul(ay.get("ilac") or [],
                         lambda v: _esit_kosul("u.UrunAdi", v))
    if p:
        parcalar.append(p)

    # Etken madde — UrunAdi VEYA ATCTurkce VEYA ATCKodu içinde ara
    # (tablo etken sütunu bu üçünden besleniyor)
    def _etken_kosul(v):
        return ("(" + _like_kosul("u.UrunAdi", v) + " OR "
                + _like_kosul("atc.ATCTurkce", v) + " OR "
                + _like_kosul("atc.ATCKodu", v) + ")")

    p = _kategori_kosul(ay.get("etken") or [], _etken_kosul)
    if p:
        parcalar.append(p)

    # ATC — kod veya Türkçe ad eşleşmesi. Akıllı eşleşme:
    #   • 1-5 karakter (anatomik/terapötik/farmakolojik grup): LIKE prefix
    #     "A10" → tüm A10AC, A10BA, A10BD ...
    #     "C10AB" → tüm C10AB01, C10AB05 ...
    #   • 7 karakter (ATC madde kodu, örn. C10AB05): tam eşitlik
    # Türkçe ad daima tam eşitlik (picker'dan gelen tam isim).
    # NULL-safe: ATC bağlantısı olmayan ürünleri içermez kuralları üzerinden
    # yanlışlıkla elememek için ISNULL ile sarılı.
    def _atc_kosul(v):
        s = str(v).strip()
        if 1 <= len(s) <= 5:
            safe = s.replace("'", "''")
            return (f"(ISNULL(atc.ATCKodu, N'') LIKE N'{safe}%' "
                    f"OR ISNULL(atc.ATCTurkce, N'') = {_q(s)})")
        return (f"(ISNULL(atc.ATCKodu, N'') = {_q(s)} "
                f"OR ISNULL(atc.ATCTurkce, N'') = {_q(s)})")

    p = _kategori_kosul(ay.get("atc") or [], _atc_kosul)
    if p:
        parcalar.append(p)

    # Farmasötik form — LIKE
    p = _kategori_kosul(ay.get("farma") or [],
                         lambda v: _like_kosul("u.UrunAdi", v))
    if p:
        parcalar.append(p)

    # Tesis — hastane kodu veya adı (subquery). EXISTS zaten NULL-safe
    # (kayıt yoksa false döner, NOT EXISTS true → satır kalır).
    def _tesis_kosul(v):
        return (f"EXISTS (SELECT 1 FROM Hastane h "
                f"WHERE h.HastaneId = ra.RxHastaneId AND "
                f"(ISNULL(h.HastaneKodu, N'') = {_q(v)} "
                f"OR ISNULL(h.HastaneAdi, N'') = {_q(v)}))")

    p = _kategori_kosul(ay.get("tesis") or [], _tesis_kosul)
    if p:
        parcalar.append(p)

    # Eşdeğer grubu — u.UrunEsdegerId numerik eşitliği.
    # Değer "12345" veya "12345 — CALPOL ŞURUP" formatında olabilir;
    # baştaki sayıyı çekip SQL'e koyarız.
    # NULL-safe: UrunEsdegerId NULL olan ürünler (eşdeğer grubu olmayanlar)
    # her bir "icermez" kuralında UNKNOWN üretip yanlışlıkla elenmesin
    # diye ISNULL(..., 0) ile 0'a çeviriyoruz (gerçek eşdeğer ID'leri 0 değil).
    import re as _re

    def _esdeger_kosul(v):
        m = _re.match(r"^\s*(\d+)", str(v))
        if not m:
            # Geçersiz değer (manuel "ABC" gibi) → kuralı eşleşmez yap.
            # NOT: önceden "1 = 0" döndürüyordu — `icerir` modunda bu
            # tüm satırları gizliyordu (sessiz tablo boşaltma).
            # `0 = 1` da eşdeğer, ama yorum açıklığı için aynı.
            return "0 = 1"
        return f"ISNULL(u.UrunEsdegerId, 0) = {int(m.group(1))}"

    p = _kategori_kosul(ay.get("esdeger") or [], _esdeger_kosul)
    if p:
        parcalar.append(p)

    return " AND ".join(parcalar)


def sql_kurum_kosullari(ay: dict) -> str:
    """Kurum sekmesindeki içerir/içermez kurallarından SQL koşulu üret.

    Bu koşul "Boş Satırları Gizle" toggle'ından BAĞIMSIZ her zaman uygulanır
    (eski `dislama_ayarlari.sql_kurum_dislama_kosulu` davranışına eşdeğer).

    İki giriş formatı desteklenir:
      • Sayı ile başlayan değer → numerik KurumId eşitliği.
        Örn picker'dan: "1234 — TÜRKİYE İŞ BANKASI A.Ş" veya düz "1234".
      • Sayı ile başlamayan değer → KurumAdi LIKE %değer% (case-insensitive).
        Örn manuel: "CEZA" → adında 'CEZA' geçen tüm kurumlar (cezaevi vb.).

    NULL toleransı: NULL kurumlu reçeteler (elden satış vb.) içermez
    kuralında DAHİL kalır — eski davranışla uyumlu.
    """
    import re as _re

    def _kurum_kosul(v: str) -> str:
        s = str(v).strip()
        if not s:
            return "1 = 0"
        m = _re.match(r"^\s*(\d+)", s)
        if m:
            # Numerik ID — picker'dan gelen "21 — MALTEPE..." veya düz "21"
            kid = int(m.group(1))
            return f"(ra.RxKurumId IS NOT NULL AND ra.RxKurumId = {kid})"
        # Manuel string girişi — KurumAdi LIKE %v% subquery
        # Örn: "CEZA" → MALTEPE 3 NOLU CEZA EVİ + diğer cezaevleri
        safe = s.replace("'", "''")
        return (f"(ra.RxKurumId IS NOT NULL AND ra.RxKurumId IN "
                f"(SELECT KurumId FROM Kurum WHERE "
                f"UPPER(KurumAdi) LIKE UPPER(N'%{safe}%')))")

    return _kategori_kosul(ay.get("kurum") or [], _kurum_kosul)


def _pattern_like_kosul(kolon: str, deger: str) -> str:
    """Pattern bazlı LIKE koşulu üret. NULL-safe.

    Pattern kuralları:
      • "M0000*"    → LIKE 'M0000%'   (suffix wildcard / prefix eşleme)
      • "*XYZ"      → LIKE '%XYZ'     (prefix wildcard / suffix eşleme)
      • "*XYZ*"     → LIKE '%XYZ%'    (her iki yan / contains)
      • "ABC"       → LIKE 'ABC%'     (yıldız yoksa default prefix)
      • "?ABC"      → LIKE '_ABC'     (? = tek karakter)

    Case-insensitive (UPPER).
    """
    s = str(deger).strip()
    if not s:
        return "1 = 0"
    if "*" in s:
        sql_pat = s.replace("*", "%")
    else:
        sql_pat = s + "%"
    sql_pat = sql_pat.replace("?", "_")
    sql_pat = sql_pat.replace("'", "''")
    return f"UPPER(ISNULL({kolon}, N'')) LIKE UPPER(N'{sql_pat}')"


def sql_sgk_kosullari(ay: dict) -> str:
    """SGK İşlem No sekmesi koşulu — toggle'dan bağımsız her zaman uygulanır.

    İki bileşen birlikte uygulanır (AND):
      1) sgk_bos_disla=True ise RxSgkIslemNo NULL/boş olan reçeteler elenir
         (apra ile satış vb. SGK olmayan reçeteler).
      2) "sgk" liste kuralları: pattern bazlı içerir/içermez
         (örn. "M0000*" → bu prefix'li reçeteler dışlanabilir).

    NOT: "icerir" modunda sadece pattern'e uyan SGK no'lar getirilir; bu
    durumda boş SGK no'lu reçeteler de elenir (whitelist mantığı).
    """
    parcalar = []

    if ay.get("sgk_bos_disla", True):
        parcalar.append(
            "(ra.RxSgkIslemNo IS NOT NULL "
            "AND LEN(LTRIM(RTRIM(ra.RxSgkIslemNo))) > 0)")

    pattern_kos = _kategori_kosul(
        ay.get("sgk") or [],
        lambda v: _pattern_like_kosul("ra.RxSgkIslemNo", v))
    if pattern_kos:
        parcalar.append(pattern_kos)

    return " AND ".join(parcalar)


def sql_doktor_kosullari(ay: dict) -> str:
    """Doktor (Hekim) sekmesi koşulu — toggle'dan bağımsız her zaman uygulanır.

    DoktorAdiSoyadi üstüne pattern eşleme:
      • "MEHMET*"     → adı MEHMET ile başlayan doktorlar
      • "*KARDIY*"    → adında KARDIY geçen doktorlar
      • "MEHMET YIL*" → tam ad prefix'i

    Kronik hasta reçetesi yazan belirli hekimleri dışlamak için.

    Subquery yaklaşımı: Doktor tablosu JOIN olmasa da çalışır. `ra` alias'lı
    ReceteAna referansı varsayılır (ra.RxDoktorId).
    NULL-safe: RxDoktorId NULL olan reçeteler içermez kuralından etkilenmez.
    """
    def _doktor_kosul(v: str) -> str:
        pat = _pattern_like_kosul("d.DoktorAdiSoyadi", v)
        return (f"EXISTS (SELECT 1 FROM Doktor d "
                f"WHERE d.DoktorId = ra.RxDoktorId AND {pat})")

    return _kategori_kosul(ay.get("doktor") or [], _doktor_kosul)


def sql_brans_kosullari(ay: dict) -> str:
    """Branş (Hekim Uzmanlık) sekmesi koşulu — toggle'dan bağımsız her zaman
    uygulanır.

    ReceteAna.RxBransId → Brans tablosu BransAdi pattern eşleme:
      • "AILE*"       → Aile Hekimi, Aile Hekimliği vs.
      • "*ACIL*"      → adında ACIL geçen branşlar
      • "KARDIY*"     → Kardiyoloji
      • "*PRATISYEN*" → Pratisyen Hekim

    Belirli branşların reçetelerini sistematik dışlamak için (örn. SUT
    kontrolünde aile hekimi reçetelerini dahil etmek istemiyorsanız).
    Subquery yaklaşımı: Brans tablosu JOIN olmasa da çalışır.
    NULL-safe: RxBransId NULL olan reçeteler içermez kuralından etkilenmez.
    """
    def _brans_kosul(v: str) -> str:
        pat = _pattern_like_kosul("b.BransAdi", v)
        return (f"EXISTS (SELECT 1 FROM Brans b "
                f"WHERE b.BransId = ra.RxBransId "
                f"AND (b.BransSilme IS NULL OR b.BransSilme = 0) "
                f"AND {pat})")

    return _kategori_kosul(ay.get("brans") or [], _brans_kosul)


# ═══════════════════════════════════════════════════════════════════════
# AYAR PENCERESİ (Toplevel dialog)
# ═══════════════════════════════════════════════════════════════════════

def _liste_secici_pencere_ac(parent, db, tip, on_select):
    """Veritabanından arama+seçim popup'ı.
    tip: 'ilac', 'etken', 'atc', 'farma', 'tesis'
    on_select(secilen_degerler_listesi, mod) — modu içerir/içermez
    """
    import tkinter as tk
    from tkinter import ttk, messagebox

    # Tipe göre SQL ve gösterim
    # Tabloda etken madde sütunu HEM ATC.ATCTurkce HEM RaporEtkinMadde'den
    # geldiği için picker iki kaynağı UNION'la birleştirir.
    SORGULAR = {
        "ilac": ("SELECT DISTINCT u.UrunAdi AS deger, '' AS ek "
                  "FROM Urun u WHERE u.UrunSilme = 0 "
                  "AND u.UrunAdi IS NOT NULL "
                  "AND LEN(u.UrunAdi) > 0 "
                  "ORDER BY u.UrunAdi", "İlaç Adı"),
        "etken": ("SELECT deger, MAX(ek) AS ek FROM ("
                   "  SELECT DISTINCT a.ATCTurkce AS deger, a.ATCKodu AS ek"
                   "  FROM ATC a "
                   "  WHERE a.ATCTurkce IS NOT NULL "
                   "    AND LEN(LTRIM(RTRIM(a.ATCTurkce))) > 0 "
                   "  UNION "
                   "  SELECT DISTINCT em.EtkinMaddeAdi AS deger, "
                   "    ISNULL(em.EtkinMaddeSGKKodu, '') AS ek "
                   "  FROM EtkinMadde em "
                   "  WHERE em.EtkinMaddeSilme = 0 "
                   "    AND em.EtkinMaddeAdi IS NOT NULL "
                   "    AND LEN(LTRIM(RTRIM(em.EtkinMaddeAdi))) > 0"
                   ") x GROUP BY deger ORDER BY deger",
                   "Etken Madde / ATC Türkçe"),
        "atc": ("SELECT a.ATCKodu AS deger, "
                 "ISNULL(a.ATCTurkce, '') AS ek "
                 "FROM ATC a "
                 "WHERE a.ATCKodu IS NOT NULL "
                 "ORDER BY a.ATCKodu", "ATC Kodu"),
        "farma": ("SELECT DISTINCT uf.UMTFarmasotikAdi AS deger, '' AS ek "
                   "FROM UMTFarmasotik uf "
                   "WHERE uf.UMTFarmasotikAdi IS NOT NULL "
                   "ORDER BY uf.UMTFarmasotikAdi", "Farmasötik Form"),
        "tesis": ("SELECT h.HastaneKodu AS deger, "
                   "ISNULL(h.HastaneAdi, '') AS ek "
                   "FROM Hastane h WHERE h.HastaneSilme = 0 "
                   "AND h.HastaneKodu IS NOT NULL "
                   "ORDER BY h.HastaneAdi", "Tesis"),
        # Kurum — picker'da "KurumId — KurumAdi" + son 365 gün reçete adedi
        "kurum": (
            "SELECT CAST(k.KurumId AS NVARCHAR(20)) + N' — ' "
            "       + ISNULL(k.KurumAdi, N'(adsız)') AS deger, "
            "       CAST(ISNULL((SELECT COUNT(DISTINCT ra.RxId) "
            "                    FROM ReceteAna ra "
            "                    WHERE ra.RxKurumId = k.KurumId "
            "                      AND ra.RxSilme = 0 "
            "                      AND ra.RxKayitTarihi >= "
            "                          DATEADD(DAY, -365, GETDATE())), 0) "
            "            AS NVARCHAR(20)) + N' reçete (1 yıl)' AS ek "
            "FROM Kurum k "
            "ORDER BY k.KurumAdi", "Kurum"),
        # Doktor (Hekim) — son 365 gün reçete adediyle birlikte
        "doktor": (
            "SELECT d.DoktorAdiSoyadi AS deger, "
            "       CAST(ISNULL((SELECT COUNT(DISTINCT ra.RxId) "
            "                    FROM ReceteAna ra "
            "                    WHERE ra.RxDoktorId = d.DoktorId "
            "                      AND ra.RxSilme = 0 "
            "                      AND ra.RxKayitTarihi >= "
            "                          DATEADD(DAY, -365, GETDATE())), 0) "
            "            AS NVARCHAR(20)) + N' reçete (1 yıl)' AS ek "
            "FROM Doktor d "
            "WHERE d.DoktorSilme = 0 "
            "  AND d.DoktorAdiSoyadi IS NOT NULL "
            "  AND LEN(LTRIM(RTRIM(d.DoktorAdiSoyadi))) > 0 "
            "ORDER BY d.DoktorAdiSoyadi", "Doktor (Hekim)"),
        # Branş — son 365 gün reçete adediyle birlikte (ReceteAna.RxBransId)
        "brans": (
            "SELECT b.BransAdi AS deger, "
            "       CAST(ISNULL((SELECT COUNT(DISTINCT ra.RxId) "
            "                    FROM ReceteAna ra "
            "                    WHERE ra.RxBransId = b.BransId "
            "                      AND ra.RxSilme = 0 "
            "                      AND ra.RxKayitTarihi >= "
            "                          DATEADD(DAY, -365, GETDATE())), 0) "
            "            AS NVARCHAR(20)) + N' reçete (1 yıl)' AS ek "
            "FROM Brans b "
            "WHERE (b.BransSilme IS NULL OR b.BransSilme = 0) "
            "  AND b.BransAdi IS NOT NULL "
            "  AND LEN(LTRIM(RTRIM(b.BransAdi))) > 0 "
            "ORDER BY b.BransAdi", "Branş (Hekim Uzmanlık)"),
        # Eşdeğer grubu — picker'da "EsdegerId — Örnek İlaç Adı" gösterir.
        # Aynı eşdeğer grubundaki tüm ilaçlar paylaşır, kullanıcı bir
        # tanesini seçince grup ID'si rule'a yazılır.
        "esdeger": (
            "SELECT CAST(g.UrunEsdegerId AS NVARCHAR(20)) "
            "       + N' — ' + ISNULL(g.OrnekIlac, N'') AS deger,"
            "       CAST(g.IlacSayisi AS NVARCHAR(10)) + N' ilaç' AS ek "
            "FROM ("
            "  SELECT u.UrunEsdegerId, "
            "         COUNT(*) AS IlacSayisi, "
            "         (SELECT TOP 1 u2.UrunAdi FROM Urun u2 "
            "          WHERE u2.UrunEsdegerId = u.UrunEsdegerId "
            "            AND u2.UrunSilme = 0 "
            "          ORDER BY u2.UrunAdi) AS OrnekIlac "
            "  FROM Urun u "
            "  WHERE u.UrunSilme = 0 "
            "    AND u.UrunEsdegerId IS NOT NULL "
            "    AND u.UrunEsdegerId > 0 "
            "  GROUP BY u.UrunEsdegerId"
            ") g "
            "ORDER BY g.OrnekIlac",
            "Eşdeğer Grubu"),
    }
    sql, baslik = SORGULAR.get(tip, ("", "Liste"))
    if not sql or db is None:
        messagebox.showinfo(
            "Bilgi", "Bu tip için veritabanı listesi mevcut değil.")
        return

    # Veriyi çek
    try:
        rows = db.sorgu_calistir(sql)
    except Exception as e:
        messagebox.showerror("Veritabanı Hatası",
                              f"{baslik} listesi okunamadı:\n{e}")
        return

    veri = []   # [(deger, ek)]
    for r in rows:
        d = (r.get("deger") or "").strip()
        if not d:
            continue
        e = (r.get("ek") or "").strip()
        veri.append((d, e))

    if not veri:
        messagebox.showinfo("Bilgi", f"{baslik} listesi boş.")
        return

    # Pencere
    win = tk.Toplevel(parent)
    win.title(f"📂 {baslik} — Listeden Seç")
    win.geometry("680x600")
    win.minsize(540, 420)
    win.configure(bg="#FAFAFA")
    win.transient(parent)

    tk.Label(win,
              text=f"📋 {baslik} listesi ({len(veri)} kayıt) — "
                   f"Ctrl/Shift ile çoklu seçim, çift tık veya butonla ekle",
              bg="#FAFAFA", fg="#37474F",
              font=("Segoe UI", 9, "bold")
              ).pack(anchor="w", padx=8, pady=(8, 4))

    # Arama kutusu
    arama_frm = tk.Frame(win, bg="#FAFAFA")
    arama_frm.pack(fill="x", padx=8, pady=2)
    tk.Label(arama_frm, text="🔍 Ara:", bg="#FAFAFA",
              font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
    var_ara = tk.StringVar()
    ent_ara = tk.Entry(arama_frm, textvariable=var_ara,
                        font=("Segoe UI", 10))
    ent_ara.pack(side="left", fill="x", expand=True)
    ent_ara.focus_set()

    # Sayım etiketi
    lbl_sayim = tk.Label(arama_frm, text="", bg="#FAFAFA", fg="#546E7A",
                          font=("Segoe UI", 9))
    lbl_sayim.pack(side="left", padx=(8, 0))

    # Treeview
    tv_frm = tk.Frame(win, bg="#FAFAFA")
    tv_frm.pack(fill="both", expand=True, padx=8, pady=4)
    sb = ttk.Scrollbar(tv_frm)
    sb.pack(side="right", fill="y")
    tv = ttk.Treeview(tv_frm, columns=("d", "e"), show="headings",
                       yscrollcommand=sb.set, selectmode="extended")
    tv.heading("d", text="Değer")
    tv.heading("e", text="Açıklama / Kod")
    tv.column("d", width=320, stretch=True)
    tv.column("e", width=320, stretch=True)
    tv.pack(side="left", fill="both", expand=True)
    sb.config(command=tv.yview)

    def _norm(s: str) -> str:
        """Türkçe karakter güvenli, büyük harfe çevirip Latin'e indirgeyen
        normalizasyon. 'FLURBİPROFEN' = 'flurbiprofen' = 'FLURBIPROFEN'
        eşleştirmesi için."""
        if not s:
            return ""
        s = s.upper()
        # Türkçe → Latin
        s = (s.replace("İ", "I").replace("I", "I").replace("Ş", "S")
              .replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O")
              .replace("Ç", "C").replace("ı", "i"))
        return s

    def _doldur(filtre=""):
        for iid in list(tv.get_children()):
            tv.delete(iid)
        flt = _norm(filtre.strip())
        n = 0
        # En fazla 5000 kayıt göster (büyük listelerde performans)
        for d, e in veri:
            if flt and flt not in _norm(d) and flt not in _norm(e):
                continue
            tv.insert("", "end", values=(d, e))
            n += 1
            if n >= 5000:
                break
        toplam = len(veri)
        if filtre.strip() and n == 0:
            lbl_sayim.config(
                text=f"⚠ '{filtre.strip()}' için 0 sonuç — "
                     f"'{baslik}' tablosunda yok. Manuel ekle.",
                fg="#B71C1C")
        else:
            lbl_sayim.config(
                text=f"Gösterilen: {n} / {toplam}", fg="#546E7A")
    _doldur()

    var_ara.trace_add("write",
                       lambda *a: _doldur(var_ara.get()))

    # Mod seçici + Ekle butonları
    bot = tk.Frame(win, bg="#ECEFF1")
    bot.pack(fill="x", side="bottom")

    mod_var = tk.StringVar(value="icermez")
    rad_frm = tk.Frame(bot, bg="#ECEFF1")
    rad_frm.pack(fill="x", padx=8, pady=(6, 2))
    tk.Label(rad_frm, text="Eklenirken mod:",
              bg="#ECEFF1", font=("Segoe UI", 9, "bold")
              ).pack(side="left")
    tk.Radiobutton(rad_frm, text="✅ İçerir (sadece bu gelsin)",
                    variable=mod_var, value="icerir", bg="#ECEFF1"
                    ).pack(side="left", padx=4)
    tk.Radiobutton(rad_frm, text="❌ İçermez (bu gelmesin)",
                    variable=mod_var, value="icermez", bg="#ECEFF1"
                    ).pack(side="left", padx=4)

    btn_frm = tk.Frame(bot, bg="#ECEFF1")
    btn_frm.pack(fill="x", padx=8, pady=(2, 6))

    def _ekle(kapat=True):
        secilenler = [tv.item(iid, "values")[0]
                      for iid in tv.selection()]
        if not secilenler:
            messagebox.showwarning("Uyarı",
                                       "Önce listeden öğe seç (Ctrl/Shift "
                                       "ile çoklu seçim).",
                                       parent=win)
            return
        try:
            on_select(secilenler, mod_var.get())
        except Exception as e:
            messagebox.showerror("Hata", f"Eklenemedi: {e}", parent=win)
            return
        if kapat:
            win.destroy()
        else:
            # Pencere açık kalsın → yeni seçim yapıp tekrar ekleyebilsin
            tv.selection_remove(*tv.selection())
            lbl_sayim.config(
                text=f"✓ {len(secilenler)} öğe eklendi — "
                     f"yeni seçim yapıp ekleyebilirsin",
                fg="#2E7D32")

    tk.Button(btn_frm, text="➕ Seçilenleri Ekle",
               bg="#1976D2", fg="white", bd=0, padx=12, pady=4,
               font=("Segoe UI", 10, "bold"),
               command=lambda: _ekle(kapat=False)).pack(side="left", padx=2)
    tk.Button(btn_frm, text="➕ Seçilenleri Ekle ve Kapat",
               bg="#43A047", fg="white", bd=0, padx=12, pady=4,
               font=("Segoe UI", 10, "bold"),
               command=lambda: _ekle(kapat=True)).pack(side="left", padx=2)
    tk.Button(btn_frm, text="❌ İptal", bg="#90A4AE", fg="white",
               bd=0, padx=10, pady=4, font=("Segoe UI", 9, "bold"),
               command=win.destroy).pack(side="right", padx=2)

    # Çift tık → seçileni ekle (tek satır) ve pencereyi kapat
    tv.bind("<Double-1>", lambda e: _ekle(kapat=True))

    win.grab_set()


def ayar_penceresini_ac(parent, db=None, on_save=None):
    """Filtre ayar penceresini aç.
    db: Botanik DB bağlantısı (Listeden Seç özelliği için)
    on_save: kaydet sonrası callback (yeni ayarları alır)."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    win = tk.Toplevel(parent)
    win.title("⚙ Aylık İnceleme — Detaylı Filtre Ayarları")
    # Tüm sekmelerde alt butonların net görünmesi için ferah boyut
    win.minsize(960, 820)
    win.resizable(True, True)
    win.configure(bg="#FAFAFA")
    win.transient(parent)
    # Ekrana ortala (ekran küçükse ekrandan taşmasın)
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        ww = min(1150, sw - 80)
        wh = min(920, sh - 80)
        x = max(0, (sw - ww) // 2)
        y = max(0, (sh - wh) // 2)
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1150x920")
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass

    ay = ayarlari_yukle()

    # ÖNEMLİ: Alt buton bar'ı sec2'nin (expand=True) önünde rezerve etmek
    # için EN ÖNCE paketleniyor (içeriği aşağıda doldurulur). Aksi halde
    # sec2 tüm alanı yutar ve alt bar görünmez kalır.
    alt = tk.Frame(win, bg="#ECEFF1")
    alt.pack(fill="x", side="bottom")

    # ════════════════════════════════════════════════════════════════
    # KOMPAKT BANNER (tek satır)
    # ════════════════════════════════════════════════════════════════
    banner = tk.Frame(win, bg="#B71C1C")
    banner.pack(fill="x")
    tk.Label(banner,
              text="🚫  Hangi Satırlar Tabloya GELSİN / GELMESİN?  ─  "
                   "Ana ekrandaki '🚫 Boş Satırları Gizle' AÇIKKEN bu "
                   "kurallar SQL'e uygulanır.",
              bg="#B71C1C", fg="white",
              font=("Segoe UI", 10, "bold"), padx=14, pady=8
              ).pack(anchor="w")

    # ════════════════════════════════════════════════════════════════
    # HIZLI PRESET — kontrol grubu seçimi için combobox
    # ════════════════════════════════════════════════════════════════
    # Presetler ATC sekmesine kural ekler. _atc_kosul akıllı eşleşme
    # yapar:
    #   • 1-5 karakter ("A10", "C10AB") → LIKE prefix → tüm alt gruplar
    #   • 7 karakter ("B01AC04") → tam eşitlik (madde kodu)
    # SQL builder içerir + içermez'i birlikte uygular: mevcut blacklist
    # kuralları korunur, sadece istenen grup gelir.
    #
    # Her preset, ana ekrandaki bir kontrol butonuyla eşleşir
    # (etiket / buton adı / kapsam birlikte gösterilir).
    PRESETLER = {
        "statin":   {"etiket": "🩺 Statin/Lipid",
                     "buton":  "STATİN KONTROL",
                     "kapsam": "ATC C10*",
                     "atc":    ["C10"]},
        "diyabet":  {"etiket": "💉 Diyabet",
                     "buton":  "DİYABET KONTROL (4.2.38)",
                     "kapsam": "ATC A10*",
                     "atc":    ["A10"]},
        "p2y12":    {"etiket": "💊 Klopidogrel/Prasugrel/Tikagrelor",
                     "buton":  "KLOPİDOGREL (4.2.15)",
                     "kapsam": "B01AC04 / B01AC22 / B01AC24",
                     "atc":    ["B01AC04", "B01AC22", "B01AC24"]},
        "arb":      {"etiket": "🩸 ARB ve Kombinasyonları",
                     "buton":  "ARB (M.51)",
                     "kapsam": "C09C* / C09D* / C02AC*",
                     "atc":    ["C09C", "C09D", "C02AC"]},
        "osteo":    {"etiket": "🦴 Kemik Erimesi (Osteoporoz)",
                     "buton":  "KEMİK ERİMESİ (4.2.17)",
                     "kapsam": "M05BA/BB/BX + H05AA + G03XC",
                     "atc":    ["M05BA", "M05BB", "M05BX",
                                "H05AA", "G03XC"]},
        "yoak":     {"etiket": "🩸 YOAK / DOAK",
                     "buton":  "YOAK (D-1/D-2)",
                     "kapsam": "B01AE07 + B01AF01/02/03",
                     "atc":    ["B01AE07", "B01AF01",
                                "B01AF02", "B01AF03"]},
        "cesitli":  {"etiket": "🧪 Çeşitli (Üriner / Gözyaşı / BPH)",
                     "buton":  "ÇEŞİTLİ (M.45 / M.2 / BPH)",
                     "kapsam": "G04BD* + G04CA* + S01XA20 + N06AX21",
                     "atc":    ["G04BD", "G04CA",
                                "S01XA20", "N06AX21"]},
        "psik":     {"etiket": "🧠 Psikiyatri / Nöroloji",
                     "buton":  "PSİKİYATRİ/NÖROLOJİ (4.2.2 + 4.2.25)",
                     "kapsam": "N05A* / N06A* / N05B* / N03A*",
                     "atc":    ["N05A", "N06A", "N05B", "N03A"]},
        "enteral":  {"etiket": "🥛 Enteral Beslenme",
                     "buton":  "ENTERAL BESLENME",
                     "kapsam": "ATC V06D*",
                     "atc":    ["V06D"]},
        "hepatit":  {"etiket": "🦠 Hepatit B/C",
                     "buton":  "HEPATİT B/C (4.2.13.3 / 4.2.13.4)",
                     "kapsam": "J05AF* / J05AP* + J05AB04 + L03AB10/11",
                     "atc":    ["J05AF", "J05AP", "J05AB04",
                                "L03AB10", "L03AB11"]},
        "astim":    {"etiket": "🌬️ Astım / KOAH",
                     "buton":  "ASTIM/KOAH (4.2.24 / 4.2.24.B)",
                     "kapsam": "ATC R03*",
                     "atc":    ["R03"]},
    }

    def _preset_combo_etiket(key):
        p = PRESETLER[key]
        return f"{p['etiket']}  —  {p['buton']}  ({p['kapsam']})"

    preset_frm = tk.LabelFrame(
        win, text=" ⚡ HIZLI PRESET  ─  Bir kontrol grubunu seçip Uygula "
                  "(ATC Grubu sekmesine İçerir kuralı ekler) ",
        bg="#E8F5E9", fg="#1B5E20",
        font=("Segoe UI", 10, "bold"), padx=8, pady=4,
        bd=2, relief="ridge")
    preset_frm.pack(fill="x", padx=10, pady=(6, 0))

    btn_row = tk.Frame(preset_frm, bg="#E8F5E9")
    btn_row.pack(fill="x", pady=2)

    tk.Label(btn_row, text="Kontrol Grubu:",
              bg="#E8F5E9", fg="#1B5E20",
              font=("Segoe UI", 9, "bold")
              ).pack(side="left", padx=(4, 6), pady=2)

    preset_keys = list(PRESETLER.keys())
    combo_values = [_preset_combo_etiket(k) for k in preset_keys]
    preset_var = tk.StringVar()
    preset_combo = ttk.Combobox(
        btn_row, textvariable=preset_var,
        values=combo_values, state="readonly",
        font=("Segoe UI", 9))
    preset_combo.pack(side="left", padx=(0, 6), pady=2,
                       fill="x", expand=True)

    preset_durum = tk.Label(
        preset_frm,
        text="ℹ Combobox'tan bir kontrol grubu seçip ✅ Uygula'ya basın → "
             "ATC Grubu sekmesine 'İçerir' kuralı eklenir (kısa ATC kodları "
             "prefix'le tüm alt grupları yakalar). Sonra 💾 Kaydet & Uygula "
             "ile SQL'de aktif olur. (İçermez kuralları korunur.)",
        bg="#E8F5E9", fg="#33691E",
        font=("Segoe UI", 9, "italic"), anchor="w", justify="left",
        wraplength=920)
    preset_durum.pack(fill="x", pady=(2, 0))

    def _preset_uygula(key):
        """ATC sekmesinin mevcut 'icerir' kurallarını siler ve preset'in
        kurallarını ekler. 'icermez' kurallarına ve diğer sekmelere dokunmaz."""
        p = PRESETLER[key]
        tv = sekmeler["atc"]["tv"]

        mevcut_icerir = [iid for iid in tv.get_children()
                          if "icerir" in (tv.item(iid, "tags") or ())]
        if mevcut_icerir:
            if not messagebox.askyesno(
                    "Preset Onay",
                    f"'{p['etiket']}' uygulanacak.\n\n"
                    f"ATC Grubu sekmesindeki {len(mevcut_icerir)} mevcut "
                    f"'İçerir' kuralı silinecek "
                    f"(İçermez kuralları korunur).\n\n"
                    f"Devam edilsin mi?",
                    parent=win):
                return
        for iid in mevcut_icerir:
            tv.delete(iid)

        eklendi = 0
        for deger in p.get("atc", []):
            tv.insert("", "end", values=("✅ İçerir", deger),
                       tags=("icerir",))
            eklendi += 1

        try:
            nb.select(list(LISTE_TIPLERI).index("atc"))
        except Exception:
            pass

        preset_durum.config(
            text=f"✅ {p['etiket']} → ATC sekmesine {eklendi} 'İçerir' "
                 f"kuralı eklendi. 💾 Kaydet & Uygula ile aktif et.",
            fg="#1B5E20")

    def _uygula_secileni():
        sec = preset_var.get().strip()
        if not sec:
            preset_durum.config(
                text="⚠ Önce combobox'tan bir kontrol grubu seçin.",
                fg="#B71C1C")
            return
        for k in preset_keys:
            if _preset_combo_etiket(k) == sec:
                _preset_uygula(k)
                return
        preset_durum.config(
            text=f"⚠ Seçim eşleşmedi: {sec}", fg="#B71C1C")

    tk.Button(btn_row, text="✅ Uygula",
               bg="#43A047", fg="white",
               activebackground="#2E7D32", bd=0,
               padx=12, pady=4,
               font=("Segoe UI", 9, "bold"),
               command=_uygula_secileni
               ).pack(side="left", padx=2, pady=2)

    # Enter ile combobox seçimi → uygula; seçim değişince durum metni
    preset_combo.bind("<Return>", lambda e: _uygula_secileni())
    preset_combo.bind(
        "<<ComboboxSelected>>",
        lambda e: preset_durum.config(
            text=f"ℹ '{preset_var.get()}' seçildi — "
                 f"✅ Uygula ile etken kuralını ekleyin.",
            fg="#33691E"))

    def _preset_temizle():
        """Tüm sekmelerden 'icerir' kurallarını siler — whitelist modu kapatır.
        'icermez' kuralları korunur."""
        toplam = 0
        for w in sekmeler.values():
            tv = w["tv"]
            toplam += sum(1 for iid in tv.get_children()
                          if "icerir" in (tv.item(iid, "tags") or ()))
        if toplam == 0:
            preset_durum.config(
                text="ℹ Hiç 'İçerir' kuralı yok — temizlenecek bir şey yok.",
                fg="#33691E")
            return
        if not messagebox.askyesno(
                "Preset Temizle",
                f"Tüm sekmelerdeki {toplam} 'İçerir' kuralı silinecek "
                f"(İçermez kuralları korunur).\n\nDevam edilsin mi?",
                parent=win):
            return
        for w in sekmeler.values():
            tv = w["tv"]
            for iid in [iid for iid in tv.get_children()
                         if "icerir" in (tv.item(iid, "tags") or ())]:
                tv.delete(iid)
        preset_durum.config(
            text=f"🧹 {toplam} 'İçerir' kuralı silindi — whitelist modu "
                 f"kapatıldı (İçermez kuralları aktif kalır).",
            fg="#1B5E20")

    tk.Button(btn_row, text="🧹 İçerir'leri Sil",
               bg="#FFE082", fg="#5D4037", bd=0,
               padx=8, pady=4,
               font=("Segoe UI", 9, "bold"),
               command=_preset_temizle
               ).pack(side="right", padx=2, pady=2)

    # ════════════════════════════════════════════════════════════════
    # SECTION 1 — İÇERİK FİLTRESİ (TEK SATIR — 4 toggle yan yana)
    # ════════════════════════════════════════════════════════════════
    var_renkli = tk.BooleanVar(value=ay.get("renkli_getir", True))
    var_mesaj = tk.BooleanVar(value=ay.get("mesaj_getir", True))
    var_uyari = tk.BooleanVar(value=ay.get("uyari_getir", True))
    var_rapor = tk.BooleanVar(value=ay.get("rapor_getir", True))

    sec1 = tk.LabelFrame(
        win, text=" 1️⃣  İÇERİK DIŞLAMA KURALLARI "
                  "(işaretliler 'boş' tanımına dahil edilir) ",
        bg="#FFEBEE", fg="#B71C1C",
        font=("Segoe UI", 10, "bold"), padx=10, pady=6,
        bd=2, relief="ridge")
    sec1.pack(fill="x", padx=10, pady=(6, 4))

    icerik_grid = tk.Frame(sec1, bg="#FFEBEE")
    icerik_grid.pack(fill="x")
    icerik_grid.columnconfigure((0, 1, 2, 3), weight=1, uniform="ic")

    icerik_secimleri = [
        (var_uyari, "⚠ Uyarısız Gelmesin",
         "Uyarı kodu OLMAYAN satırlar boş kabul edilsin"),
        (var_mesaj, "💬 Mesajsız Gelmesin",
         "İlaç mesajı OLMAYAN satırlar boş kabul edilsin"),
        (var_rapor, "📋 Raporsuz Gelmesin",
         "Rapor kodu OLMAYAN satırlar boş kabul edilsin"),
        (var_renkli, "🟥🟩🟪 Beyaz Reçete Gelmesin",
         "Kırmızı/Yeşil/Mor olmayan beyaz reçeteler boş kabul edilsin"),
    ]
    for i, (v, baslik, tip_text) in enumerate(icerik_secimleri):
        kart = tk.Frame(icerik_grid, bg="white", bd=1, relief="solid")
        kart.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
        cb = tk.Checkbutton(kart, text=baslik, variable=v, bg="white",
                             font=("Segoe UI", 10, "bold"), fg="#B71C1C",
                             padx=4, pady=4)
        cb.pack(anchor="w")
        # Tooltip yerine küçük bir alt metin
        tk.Label(kart, text=tip_text, bg="white", fg="#546E7A",
                 font=("Segoe UI", 8), wraplength=240,
                 justify="left").pack(anchor="w", padx=24, pady=(0, 4))

    # Canlı önizleme — tek satır
    onizleme_lbl = tk.Label(sec1, text="", bg="#FFF9C4", fg="#5D4037",
                              font=("Consolas", 9, "bold"),
                              anchor="w", padx=8, pady=4,
                              bd=1, relief="solid")
    onizleme_lbl.pack(fill="x", pady=(4, 0))

    def _onizleme_guncelle(*_):
        kurallar = []
        if var_uyari.get():    kurallar.append("uyarı yok")
        if var_mesaj.get():    kurallar.append("mesaj yok")
        if var_rapor.get():    kurallar.append("rapor yok")
        if var_renkli.get():   kurallar.append("beyaz reçete")
        if not kurallar:
            txt = ("✅ Hiçbir dışlama kuralı işaretli değil — "
                   "tüm satırlar tabloya gelir.")
        else:
            txt = "🚫 GETİRME koşulu:  " + "  VE  ".join(kurallar)
        onizleme_lbl.config(text=txt)

    for v in (var_uyari, var_mesaj, var_rapor, var_renkli):
        v.trace_add("write", _onizleme_guncelle)
    _onizleme_guncelle()

    # ════════════════════════════════════════════════════════════════
    # SECTION 2 — LİSTE BAZLI KURALLAR (notebook ile, tüm kalan alanı dolduruyor)
    # ════════════════════════════════════════════════════════════════
    sec2 = tk.LabelFrame(
        win,
        text=" 2️⃣  LİSTE BAZLI KURALLAR  ─  Veritabanından seç veya manuel ekle ",
        bg="#FFF8E1", fg="#E65100",
        font=("Segoe UI", 10, "bold"),
        padx=6, pady=4, bd=2, relief="ridge")
    sec2.pack(fill="both", expand=True, padx=10, pady=(0, 4))

    nb = ttk.Notebook(sec2)
    nb.pack(fill="both", expand=True, padx=2, pady=2)

    # Her tip için açıklama metni
    SEKME_ACIKLAMALARI = {
        "ilac": ("🏷️ Tam ilaç adı eşleşmesi (UrunAdi). Örn: "
                  "'TRAVAZOL %1+%0,1 KREM (15 G)'. Liste içinden "
                  "seçilenler eşit (=) karşılaştırmasıyla SQL'de filtrelenir."),
        "etken": ("🧪 Etken madde adının ilaç adı içinde geçtiği satırlar. "
                   "LIKE %X% kullanır. Örn: 'METFORMIN' yazınca tüm "
                   "metformin içeren ilaçlar etkilenir."),
        "atc": ("🧬 ATC kodu veya Türkçe adı (Urun.UrunATCId → ATC tablosu). "
                 "Akıllı eşleşme: 1-5 karakter (ör. 'A10', 'C10AB') → "
                 "PREFIX yakalar (A10AC01, A10BA02... hepsi gelir). "
                 "7 karakter (ör. 'C10AB05') → tam madde kodu eşleşmesi."),
        "farma": ("💊 Farmasötik form — ilaç adında geçen anahtar kelime. "
                   "LIKE %X% kullanır. Örn: 'KREM', 'ŞURUP', 'AMPUL'."),
        "tesis": ("🏥 Hastane kodu veya adı (Hastane tablosu). "
                   "Örn: '11340187' veya 'BAĞCILAR EĞİTİM HASTANESİ'."),
        "esdeger": ("🔁 Eşdeğer grubu — aynı etken/doz/form'a sahip "
                     "ilaçlar tek bir grup ID'si paylaşır. Bir CALPOL ŞURUP "
                     "seçtiğinde tüm muadil şuruplar (PAROL, TYLOL vb.) "
                     "aynı kuralla etkilenir. Picker'da ID + örnek ilaç adı "
                     "görürsün; SQL filtresi UrunEsdegerId ile çalışır."),
        "kurum": ("🚫 Kurum (eski 'Dışlamalar' butonunun yerine geçer). "
                   "İki giriş formatı: ① Listeden seç → 'KurumId — Ad' "
                   "(o tek kurum). ② Manuel → adın bir kısmını yaz "
                   "(örn. 'CEZA') → adında bu metin geçen TÜM kurumları "
                   "kapsar (KurumAdi LIKE %değer%). İçermez moduyla bu "
                   "kurumların reçeteleri tüm sorgulardan ve SUT "
                   "kontrollerinden çıkar. ÖNEMLİ: Kurum kuralları 'Boş "
                   "Satırları Gizle' toggle'ından BAĞIMSIZ HER ZAMAN "
                   "uygulanır. NULL kurumlu reçeteler (elden satış vb.) "
                   "içermez kuralında dahil kalır."),
        "sgk": ("🔢 SGK İşlem No (RxSgkIslemNo) bazlı dışlama. "
                 "ÜSTTEKİ TOGGLE: 'SGK işlem no boş olanları gizle' (default "
                 "AÇIK) — sistem reçete no'su olmayan reçeteler (apra ile "
                 "satılmış vb. SGK olmayan reçeteler) tablodan hiç gelmez. "
                 "PATTERN LİSTESİ: belirli formatlardaki SGK no'larını "
                 "dışla. Pattern kuralları: 'M0000*' (prefix), '*XYZ' "
                 "(suffix), '*ABC*' (contains), 'ABC' (yıldızsız=prefix). "
                 "Örn: 'M0000*' kuralı + İçermez modu → M0000... ile "
                 "başlayan tüm reçeteler elenir. Bu sekmenin kuralları "
                 "'Boş Satırları Gizle' toggle'ından BAĞIMSIZ her zaman "
                 "uygulanır (Kurum sekmesi gibi)."),
        "doktor": ("👨‍⚕️ Doktor (Hekim) adı bazlı dışlama "
                    "(DoktorAdiSoyadi). Pattern eşleme: 'MEHMET*' (ile "
                    "başlayan), '*YILMAZ' (ile biten), '*KARDIY*' (içeren). "
                    "Yıldızsız değer prefix kabul edilir. Kullanım: kronik "
                    "hasta reçetesi yazan belirli hekimleri sistematik "
                    "dışlamak için. İçermez moduyla bu hekimlerin "
                    "reçeteleri tüm sorgulardan ve SUT kontrollerinden "
                    "çıkar. Bu sekmenin kuralları 'Boş Satırları Gizle' "
                    "toggle'ından BAĞIMSIZ her zaman uygulanır."),
        "brans": ("🏥 Branş (Hekim Uzmanlık) bazlı dışlama "
                   "(ReceteAna.RxBransId → Brans.BransAdi). Pattern "
                   "eşleme: 'AILE*' (Aile Hekimi/Hekimliği), '*ACIL*' "
                   "(adında ACIL geçen), 'KARDIY*' (Kardiyoloji), "
                   "'*PRATISYEN*'. Yıldızsız değer prefix kabul edilir. "
                   "Kullanım: belirli branşların reçetelerini sistematik "
                   "dışlamak (örn. Aile Hekimi'nin yazdığı tüm reçeteleri "
                   "SUT kontrolünden çıkarmak). İçermez moduyla bu "
                   "branşların reçeteleri tüm sorgulardan çıkar. "
                   "DİKKAT: doktor sekmesindeki ad pattern'i ile karıştırma "
                   "— bu sekme reçete üzerindeki RxBransId'yi kontrol "
                   "eder (bir doktor birden fazla branşta reçete yazabilir, "
                   "doğrudan o reçeteye yazılan branş esas alınır). Bu "
                   "sekmenin kuralları 'Boş Satırları Gizle' toggle'ından "
                   "BAĞIMSIZ her zaman uygulanır."),
    }

    # SGK boş dışla toggle — sgk sekmesinin içine inject edilecek (aşağıda)
    var_sgk_bos = tk.BooleanVar(value=ay.get("sgk_bos_disla", True))

    # Her tip için aynı arayüz — per-item içerir/içermez
    sekmeler = {}
    for tip in LISTE_TIPLERI:
        kurallar = ay.get(tip) or []
        sekme = tk.Frame(nb, bg="#FAFAFA")
        nb.add(sekme, text=LISTE_ETIKETLERI[tip])

        # Açıklama
        tk.Label(sekme, text=SEKME_ACIKLAMALARI.get(tip, ""),
                  bg="#FFFDE7", fg="#5D4037",
                  font=("Segoe UI", 9), justify="left",
                  wraplength=800, anchor="w", padx=8, pady=4,
                  bd=1, relief="solid"
                  ).pack(fill="x", padx=8, pady=(8, 4))

        # SGK sekmesi için özel toggle: SGK işlem no boş olanları dışla
        if tip == "sgk":
            toggle_frm = tk.LabelFrame(
                sekme, text=" 🚫 Toggle ", bg="#FFF3E0", fg="#E65100",
                font=("Segoe UI", 9, "bold"), padx=6, pady=4)
            toggle_frm.pack(fill="x", padx=8, pady=(0, 4))
            tk.Checkbutton(
                toggle_frm,
                text="SGK işlem no BOŞ olan reçeteleri dışla "
                     "(apra/özel satış reçeteleri = SGK olmayan reçeteler)",
                variable=var_sgk_bos, bg="#FFF3E0",
                font=("Segoe UI", 10, "bold"), fg="#E65100",
                padx=4, pady=2
            ).pack(anchor="w")
            tk.Label(
                toggle_frm,
                text="✓ AÇIK (önerilen): RxSgkIslemNo NULL/boş olan "
                     "reçeteler tüm sorgulardan elenir; YOAK, statin, "
                     "tüm SUT kontrolleri etkilenir.\n"
                     "○ KAPALI: SGK olmayan reçeteler de listeye gelir.",
                bg="#FFF3E0", fg="#6D4C41",
                font=("Segoe UI", 8, "italic"),
                anchor="w", justify="left", padx=24
            ).pack(anchor="w")

        # Kural listesi (Treeview: Mod | Değer)
        tv_frm = tk.Frame(sekme, bg="#FAFAFA")
        tv_frm.pack(fill="both", expand=True, padx=8, pady=4)

        sb = ttk.Scrollbar(tv_frm)
        sb.pack(side="right", fill="y")
        tv = ttk.Treeview(tv_frm, columns=("mod", "deger"),
                            show="headings", height=8,
                            yscrollcommand=sb.set, selectmode="browse")
        tv.heading("mod", text="Mod")
        tv.heading("deger", text="Değer")
        tv.column("mod", width=110, stretch=False, anchor="w")
        tv.column("deger", width=600, stretch=True, anchor="w")
        tv.pack(side="left", fill="both", expand=True)
        sb.config(command=tv.yview)
        # Renk tag'leri
        tv.tag_configure("icerir", background="#E8F5E9", foreground="#1B5E20")
        tv.tag_configure("icermez", background="#FFEBEE", foreground="#B71C1C")

        # Mevcut kuralları yükle
        for kural in kurallar:
            mod = kural.get("mod", "icerir")
            deger = kural.get("deger", "")
            etiket = "✅ İçerir" if mod == "icerir" else "❌ İçermez"
            tv.insert("", "end", values=(etiket, deger), tags=(mod,))

        # ── Yeni kural ekleme bar ──
        ekle_frm = tk.LabelFrame(sekme, text=" ➕ Yeni Kural Ekle ",
                                    bg="#E3F2FD", fg="#0D47A1",
                                    font=("Segoe UI", 9, "bold"))
        ekle_frm.pack(fill="x", padx=8, pady=4)

        yeni_mod_var = tk.StringVar(value="icermez")
        rad_frm = tk.Frame(ekle_frm, bg="#E3F2FD")
        rad_frm.pack(fill="x", padx=4, pady=4)
        tk.Label(rad_frm, text="Mod:", bg="#E3F2FD",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=(2, 6))
        tk.Radiobutton(rad_frm, text="✅ İçerir (sadece bu gelsin)",
                        variable=yeni_mod_var, value="icerir",
                        bg="#E3F2FD"
                        ).pack(side="left", padx=4)
        tk.Radiobutton(rad_frm, text="❌ İçermez (bu gelmesin)",
                        variable=yeni_mod_var, value="icermez",
                        bg="#E3F2FD"
                        ).pack(side="left", padx=4)

        # Listeden seç butonu — DB'den arama+seçim popup'ı açar
        def _liste_ac(tv=tv, mod_var=yeni_mod_var, _tip=tip):
            def _on_secim(degerler, mod):
                for v in degerler:
                    v = (v or "").strip()
                    if not v:
                        continue
                    # Aynı (mod, deger) varsa atla
                    var = False
                    for iid in tv.get_children():
                        vals = tv.item(iid, "values")
                        tags = tv.item(iid, "tags") or ()
                        if vals[1] == v and (
                                ("icerir" in tags and mod == "icerir") or
                                ("icermez" in tags and mod == "icermez")):
                            var = True
                            break
                    if var:
                        continue
                    etiket = "✅ İçerir" if mod == "icerir" else "❌ İçermez"
                    tv.insert("", "end", values=(etiket, v), tags=(mod,))
            _liste_secici_pencere_ac(win, db, _tip, _on_secim)

        tk.Button(rad_frm, text="📂 Veritabanından Listeden Seç...",
                   bg="#1976D2", fg="white", bd=0, padx=10, pady=2,
                   font=("Segoe UI", 9, "bold"),
                   command=_liste_ac
                   ).pack(side="right", padx=4)

        # Manuel giriş satırı (mevcut)
        ent_frm = tk.Frame(ekle_frm, bg="#E3F2FD")
        ent_frm.pack(fill="x", padx=4, pady=(0, 4))
        tk.Label(ent_frm, text="Manuel:", bg="#E3F2FD",
                  font=("Segoe UI", 9)).pack(side="left", padx=(2, 4))
        ent_yeni = tk.Entry(ent_frm, font=("Segoe UI", 10))
        ent_yeni.pack(side="left", fill="x", expand=True, padx=(0, 4))

        def _ekle(tv=tv, ent=ent_yeni, mv=yeni_mod_var):
            v = (ent.get() or "").strip()
            if not v:
                return
            # Aynı (mod, değer) varsa atla
            for iid in tv.get_children():
                vals = tv.item(iid, "values")
                if vals[1] == v and (
                        ("icerir" in vals[0] and mv.get() == "icerir") or
                        ("İçermez" in vals[0] and mv.get() == "icermez")):
                    ent.delete(0, tk.END)
                    return
            mod = mv.get()
            etiket = "✅ İçerir" if mod == "icerir" else "❌ İçermez"
            tv.insert("", "end", values=(etiket, v), tags=(mod,))
            ent.delete(0, tk.END)

        def _sil(tv=tv):
            for iid in list(tv.selection()):
                tv.delete(iid)

        def _modu_degistir(tv=tv):
            # Seçili satırların modunu içerir↔içermez tersine çevir
            for iid in list(tv.selection()):
                vals = tv.item(iid, "values")
                tags = tv.item(iid, "tags") or ()
                yeni = "icermez" if "icerir" in tags else "icerir"
                etiket = "✅ İçerir" if yeni == "icerir" else "❌ İçermez"
                tv.item(iid, values=(etiket, vals[1]), tags=(yeni,))

        def _temizle(tv=tv):
            if messagebox.askyesno(
                    "Onay",
                    "Bu listedeki tüm kuralları silmek istediğine "
                    "emin misin?"):
                for iid in list(tv.get_children()):
                    tv.delete(iid)

        tk.Button(ent_frm, text="➕ Ekle", bg="#43A047", fg="white",
                   bd=0, padx=10, command=_ekle,
                   font=("Segoe UI", 9, "bold")
                   ).pack(side="left", padx=2)

        # Çift tık → mod değiştir
        tv.bind("<Double-1>", lambda e, fn=_modu_degistir: fn())
        # Enter → ekle
        ent_yeni.bind("<Return>", lambda e, fn=_ekle: fn())

        # ── Liste işlemleri butonları ──
        btn_frm = tk.Frame(sekme, bg="#FAFAFA")
        btn_frm.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(btn_frm, text="🔄 Modu Değiştir",
                   bg="#1976D2", fg="white", bd=0, padx=10,
                   command=_modu_degistir
                   ).pack(side="left", padx=2)
        tk.Button(btn_frm, text="➖ Seçileni Sil",
                   bg="#E53935", fg="white", bd=0, padx=10,
                   command=_sil
                   ).pack(side="left", padx=2)
        tk.Button(btn_frm, text="🧹 Tümünü Temizle",
                   bg="#FFE082", fg="#5D4037", bd=0, padx=10,
                   command=_temizle
                   ).pack(side="left", padx=2)
        tk.Label(btn_frm, text=" 💡 Çift tık ile satırın modunu hızlı "
                                "değiştirebilirsin",
                  bg="#FAFAFA", fg="#546E7A",
                  font=("Segoe UI", 8, "italic")
                  ).pack(side="left", padx=8)

        sekmeler[tip] = {"tv": tv}

    # ───── ALT BUTON BAR İÇERİĞİ (frame zaten yukarıda paketlendi) ─────

    def _kaydet_kapat():
        yeni = {
            "renkli_getir":  var_renkli.get(),
            "mesaj_getir":   var_mesaj.get(),
            "uyari_getir":   var_uyari.get(),
            "rapor_getir":   var_rapor.get(),
            "sgk_bos_disla": var_sgk_bos.get(),
        }
        for tip, w in sekmeler.items():
            tv = w["tv"]
            kurallar = []
            for iid in tv.get_children():
                vals = tv.item(iid, "values")
                tags = tv.item(iid, "tags") or ()
                mod = "icerir" if "icerir" in tags else "icermez"
                kurallar.append({"deger": vals[1], "mod": mod})
            yeni[tip] = kurallar
        ayarlari_kaydet(yeni)
        if on_save:
            try:
                on_save(yeni)
            except Exception as e:
                logger.exception("on_save hatası: %s", e)
        win.destroy()

    def _varsayilana_don():
        if not messagebox.askyesno("Onay",
                                       "Tüm ayarlar varsayılana dönecek "
                                       "(4 içerik açık, liste kuralları "
                                       "boş). Devam edilsin mi?"):
            return
        var_renkli.set(True)
        var_mesaj.set(True)
        var_uyari.set(True)
        var_rapor.set(True)
        var_sgk_bos.set(True)
        for w in sekmeler.values():
            tv = w["tv"]
            for iid in list(tv.get_children()):
                tv.delete(iid)

    tk.Button(alt, text="↺ Varsayılana Dön", bg="#FFE082", fg="#5D4037",
               bd=0, padx=10, command=_varsayilana_don,
               font=("Segoe UI", 9, "bold")
               ).pack(side="left", padx=8, pady=8)
    tk.Button(alt, text="❌ İptal", bg="#90A4AE", fg="white",
               bd=0, padx=12, command=win.destroy,
               font=("Segoe UI", 9, "bold")
               ).pack(side="right", padx=4, pady=8)
    tk.Button(alt, text="💾 Kaydet & Uygula", bg="#1976D2", fg="white",
               bd=0, padx=12, command=_kaydet_kapat,
               font=("Segoe UI", 9, "bold")
               ).pack(side="right", padx=4, pady=8)

    win.grab_set()
