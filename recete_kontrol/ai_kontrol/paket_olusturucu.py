"""AI'a Gönderilecek Veri Paketini Hazırla.

Aylık reçete sorgu tablosundaki bir satır + Botanik DB ek sorguları →
anonimleştirilmiş JSON paket. AI bu paketi sistem prompt'undaki SUT
bilgisi ile karşılaştırıp UYGUN/UYGUN_DEGIL/ŞÜPHELİ/KE kararı verir.

Anonimleştirme (KVKK Madde 6 uyumlu):
    • MusteriTCKN     → SHA-256[:16] hash (sadece tutarlılık için)
    • MusteriAdiSoyadi→ "HASTA" (atılır)
    • MusteriDogumTarihi → yaş + cinsiyet (ham tarih gönderilmez)
    • DoktorAdiSoyadi  → "DOKTOR" (atılır; branş kalır)

Faz 1: SADECE Botanik DB kaynağı.
Faz 2 (2026-07-05): Medula canlı entegrasyonu — `medula_kullan=True` ise
`medula_hasta_toplayici` ile hastanın Medula ilaç geçmişi (çapraz-reçete)
ve rapor geçmişi (bitmiş dahil) toplanıp `kaynak` etiketiyle Botanik EOS
verilerine eklenir. Medula SADECE OKUNUR (CLAUDE.md kırmızı çizgi).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# YARDIMCILAR — anonimleştirme + tip normalize
# ──────────────────────────────────────────────────────────────────────

def _tc_hash(tc: Any) -> str:
    if not tc:
        return ""
    return hashlib.sha256(str(tc).encode("utf-8")).hexdigest()[:16]


def _yas_hesapla(dogum: Any, ref_tarih: Optional[date] = None) -> Optional[int]:
    """Doğum tarihinden yaş hesapla (yıl bazlı)."""
    if not dogum:
        return None
    try:
        if hasattr(dogum, "year"):
            d = dogum
        else:
            s = str(dogum)
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    d = datetime.strptime(s[:19] if " " in s else s, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
        ref = ref_tarih or date.today()
        yil = ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))
        return max(0, int(yil))
    except Exception:
        return None


def _tarihi_iso(d: Any) -> str:
    """Tarih objesini/string'ini ISO formata getir (YYYY-MM-DD)."""
    if not d:
        return ""
    if hasattr(d, "isoformat"):
        try:
            return d.isoformat()[:10]
        except Exception:
            pass
    s = str(d).strip()
    if not s:
        return ""
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return s[:10]


def _cinsiyet_normalize(c: Any) -> str:
    """Cinsiyet kodunu metin formata çevir."""
    if c is None:
        return ""
    s = str(c).strip().upper()
    if s in ("E", "M", "MALE", "ERKEK", "1"):
        return "Erkek"
    if s in ("K", "F", "FEMALE", "KADIN", "KADİN", "2"):
        return "Kadın"
    return s or ""


# ──────────────────────────────────────────────────────────────────────
# ANA PAKET OLUŞTURUCU
# ──────────────────────────────────────────────────────────────────────

@dataclass
class PaketKonfig:
    """Paket oluşturma seçenekleri."""
    botanik_db_kullan: bool = True
    medula_kullan: bool = False    # True → Medula'da gezinerek canlı toplama
                                   # (yavaş: ~1-2 dk/hasta; GUI checkbox)
    medula_rapor_detayli: bool = True  # her rapora girip detay metni oku
    ilac_gecmisi_ay: int = 24      # Botanik DB'den kaç ay geriye bakılsın
    rapor_gecmisi_yil: int = 5     # Kaç yıllık eski rapor dahil
    max_recete_ilac: int = 50      # Reçetenin diğer ilaçları max sayı
    max_hasta_ilac: int = 100      # Hasta geçmiş ilaç max sayı (kaynak başına)


def paket_olustur(
    satir: Dict[str, Any],
    *,
    konfig: Optional[PaketKonfig] = None,
    db: Any = None,
    durum_cb: Any = None,
) -> Dict[str, Any]:
    """Bir aylık-tablo satırından AI'a gönderilecek anonim JSON paketi üret.

    Args:
        satir: aylik_recete_sorgu_gui satır verisi (sütun → değer dict)
        konfig: PaketKonfig — varsayılan: Botanik DB aktif, Medula pasif
        db: BotanikDB instance (None ise yeni açılır)
        durum_cb: opsiyonel durum callback'i (Medula gezinme ilerleme
            mesajları — GUI'de göstermek için)

    Returns:
        {
          "recete": {...},          # tek reçete (kullanılan ilaç dahil)
          "hasta": {...},           # anonim hasta klinik veri
          "rapor": {...} | null,    # eşleşen rapor (varsa)
          "hasta_diger_raporlari": [...],  # son N yıl
          "hasta_ilac_gecmisi": [...],     # son N ay
          "kaynak_etiketleri": {"botanik_db": true, "medula": false},
          "metadata": {...}
        }
    """
    cfg = konfig or PaketKonfig()
    paket: Dict[str, Any] = {
        "metadata": {
            "olusum_tarihi": datetime.now().isoformat(timespec="seconds"),
            "paket_versiyon": "1.1-faz2" if cfg.medula_kullan else "1.0-faz1",
        },
        "kaynak_etiketleri": {
            "botanik_db": bool(cfg.botanik_db_kullan),
            "medula": bool(cfg.medula_kullan),
        },
    }

    paket["recete"] = _recete_bolumu_olustur(satir)
    paket["hasta"] = _hasta_bolumu_olustur(satir)
    paket["rapor"] = _rapor_bolumu_olustur(satir)

    paket["hasta_diger_raporlari"] = []
    paket["hasta_ilac_gecmisi"] = []
    paket["endikasyon_disi_izinler"] = []
    paket["uyarilar"] = []

    if cfg.botanik_db_kullan:
        try:
            ek = _botanik_db_ek_veri(satir, cfg, db=db)
            paket["hasta_diger_raporlari"] = ek.get("hasta_diger_raporlari", [])
            paket["hasta_ilac_gecmisi"] = ek.get("hasta_ilac_gecmisi", [])
            paket["recete_diger_ilaclari"] = ek.get("recete_diger_ilaclari", [])
            paket["uyarilar"].extend(ek.get("uyarilar", []))
            # Aktif rapor zenginleştirme — paket["rapor"]'a merge et
            rapor_detay = ek.get("rapor_detay") or {}
            if rapor_detay and paket.get("rapor"):
                paket["rapor"]["icd_listesi"] = rapor_detay.get("icd_listesi", [])
                paket["rapor"]["etken_madde_listesi"] = rapor_detay.get(
                    "etken_madde_listesi", [])
                paket["rapor"]["ek_bilgiler"] = rapor_detay.get("ek_bilgiler", [])
                paket["rapor"]["rapor_doktor_uzmanliklari"] = rapor_detay.get(
                    "rapor_doktor_uzmanliklari", [])
        except Exception as e:
            logger.error("Botanik DB ek veri toplama hatası: %s", e, exc_info=True)
            paket["uyarilar"].append({
                "kaynak": "botanik_db",
                "hata": f"Botanik DB sorgusu başarısız: {e}",
            })

    # Kaynak etiketi — EOS kayıtları (Medula'yla ayırt edilebilsin)
    for kayit in paket["hasta_diger_raporlari"]:
        kayit.setdefault("kaynak", "botanik_eos")
    for kayit in paket["hasta_ilac_gecmisi"]:
        kayit.setdefault("kaynak", "botanik_eos")

    if cfg.medula_kullan:
        try:
            _medula_ek_veri(satir, cfg, paket, durum_cb=durum_cb)
        except Exception as e:
            logger.error("Medula ek veri toplama hatası: %s", e, exc_info=True)
            paket["uyarilar"].append({
                "kaynak": "medula",
                "hata": f"Medula toplama başarısız: {e}",
            })

    paket["veri_kapsami"] = _veri_kapsami_ozeti(paket)
    return paket


def _ddmmyyyy_iso(s: Any) -> str:
    """Medula tarih formatını (dd/mm/yyyy) ISO'ya çevir; olmazsa aynen dön."""
    t = str(s or "").strip()
    if len(t) == 10 and t[2] == "/" and t[5] == "/":
        return f"{t[6:10]}-{t[3:5]}-{t[0:2]}"
    return t


def _medula_ek_veri(
    satir: Dict[str, Any],
    cfg: PaketKonfig,
    paket: Dict[str, Any],
    durum_cb: Any = None,
) -> None:
    """Medula'da gezinerek hastanın ilaç + rapor geçmişini topla ve paketi
    yerinde zenginleştir (kaynak='medula' etiketiyle).

    • Rapor geçmişi → `hasta_diger_raporlari`'na eklenir; EOS'ta zaten
      bulunan raporlar rapor_takip_no ile DEDUP edilir (EOS zengin verisi
      öncelikli, Medula sadece EOS'ta olmayanları getirir).
    • İlaç geçmişi → `hasta_ilac_gecmisi`'ne eklenir (çapraz-reçete SGK
      geçmişi: başka eczaneler dahil — EOS'tan geniş kapsam).
    Medula SADECE OKUNUR; toplayıcı modül kilitle serileştirir.
    """
    tc = str(satir.get("MusteriTCKN") or satir.get("hasta_tc")
             or satir.get("tc") or "").strip()
    if not (len(tc) == 11 and tc.isdigit()):
        paket["uyarilar"].append({
            "kaynak": "medula",
            "not": "Hasta TC satırda yok/geçersiz — Medula toplama atlandı",
        })
        return

    # Aktif reçetenin rapor kodu → sadece ilgili raporlar detaylı okunsun
    # (hepsine girmek çok yavaş; liste metadata'sı yine TÜM raporlar için gelir)
    rapor_kodu = str(satir.get("sr_rapor_kodu") or satir.get("rapor_kodu")
                     or satir.get("rap_kod") or "").strip() or None

    from recete_kontrol.medula_hasta_toplayici import medula_hasta_verisi_topla
    veri = medula_hasta_verisi_topla(
        tc,
        cb=durum_cb,
        rapor_detayli=cfg.medula_rapor_detayli,
        rapor_kodu_filtre=rapor_kodu,
    )

    for hata in veri.get("hatalar") or []:
        paket["uyarilar"].append({"kaynak": "medula", "hata": str(hata)})

    # ── Rapor geçmişi birleştirme (rapor_takip_no dedup) ──
    eos_takipler = {
        str(r.get("rapor_takip_no") or "").strip()
        for r in paket.get("hasta_diger_raporlari") or []
        if str(r.get("rapor_takip_no") or "").strip()
    }
    eklenen_rapor = 0
    for r in veri.get("rapor_gecmisi") or []:
        takip = str(r.get("rapor_takip_no") or "").strip()
        if takip and takip in eos_takipler:
            continue  # EOS'ta zaten var (zenginleştirilmiş hâliyle)
        paket["hasta_diger_raporlari"].append({
            "rapor_no": takip,
            "rapor_takip_no": takip,
            "rapor_tarihi": _ddmmyyyy_iso(r.get("baslangic_tarihi")),
            "bitis_tarihi": _ddmmyyyy_iso(r.get("bitis_tarihi")),
            "rapor_metni": str(r.get("detay_metni") or "")[:4000],
            "icd_listesi": (
                [{"icd_kodu": str(r.get("icd_kodu")), "aciklama": ""}]
                if r.get("icd_kodu") else []),
            "etken_madde_listesi": [],
            "ek_bilgiler": [],
            "rapor_doktor_uzmanliklari": [],
            "rapor_kodlari": (
                [{"kod": str(r.get("rapor_kodu")),
                  "aciklama": str(r.get("tani") or "")}]
                if r.get("rapor_kodu") else []),
            "rapor_tipi": str(r.get("rapor_tipi") or ""),
            "tani": str(r.get("tani") or ""),
            "kaynak": "medula",
        })
        eklenen_rapor += 1

    # ── İlaç geçmişi birleştirme ──
    # Medula listesi çapraz-reçete (başka eczaneler dahil) — dedup edilmez,
    # kaynak etiketi AI'a hangi listenin nereden geldiğini söyler.
    ilaclar = veri.get("ilac_gecmisi") or []
    ilaclar = ilaclar[: max(0, int(cfg.max_hasta_ilac))]
    for k in ilaclar:
        paket["hasta_ilac_gecmisi"].append({
            "tarih": _ddmmyyyy_iso(k.get("recete_tarihi")),
            "urun_adi": str(k.get("ilac_adi") or ""),
            "adet": _safe_int(k.get("adet")),
            "kullanim": str(k.get("kullanim") or ""),
            "ilac_alim_tarihi": _ddmmyyyy_iso(k.get("ilac_alim_tar")),
            "recete_no": str(k.get("recete_no") or ""),
            "rapor_teshis_takip": str(k.get("teshis_raptak") or ""),
            "kaynak": "medula",
        })

    # ── Endikasyon dışı izinler (sadece Medula'da var) ──
    # SUT denetimi için kritik: onaylı endikasyon dışı kullanım izni,
    # doz/süre onayı ve değerlendirme uzmanı açıklaması detay metninde.
    paket["endikasyon_disi_izinler"] = [{
        "basvuru_no": str(e.get("basvuru_no") or ""),
        "basvuru_tarihi": _ddmmyyyy_iso(e.get("basvuru_tarihi")),
        "onay_tarihi": _ddmmyyyy_iso(e.get("onay_tarihi")),
        "durumu": str(e.get("durumu") or ""),
        "saglik_tesisi": str(e.get("saglik_tesisi") or ""),
        "basvuru_nedeni": str(e.get("basvuru_nedeni") or ""),
        "detay_metni": str(e.get("detay_metni") or "")[:4000],
        "kaynak": "medula",
    } for e in veri.get("endikasyon_disi") or []]

    logger.info("Medula ek veri: +%d rapor, +%d ilaç, +%d end.dışı izin "
                "(TC %s****)", eklenen_rapor, len(ilaclar),
                len(paket["endikasyon_disi_izinler"]), tc[:3])


def _veri_kapsami_ozeti(paket: Dict[str, Any]) -> Dict[str, Any]:
    """Paket'in hangi alanlarının dolu/boş olduğunu özetle.

    AI prompt'unda bu özet AI'a 'elindeki veriyle ne yapabileceğini' söyler;
    AI artık kolayca 'YETERSIZ_VERI' diyemez — elindekiyle karar vermek
    zorunda. Aynı zamanda kullanıcı Önizle dialogunda anında görür.
    """
    recete = paket.get("recete") or {}
    ilac = recete.get("ilac") or {}
    rapor = paket.get("rapor") or {}
    rapor_metni = (rapor.get("rapor_metni") or "") if rapor else ""

    return {
        "recete_no_var": bool(recete.get("recete_no")),
        "ilac_adi_var": bool(ilac.get("urun_adi")),
        "atc_kodu_var": bool(ilac.get("atc_kodu")),
        "recete_teshis_var": bool(recete.get("recete_teshis")),
        "recete_aciklama_var": bool(recete.get("recete_aciklama")),
        "rapor_var": bool(rapor),
        "rapor_metni_uzunluk": len(rapor_metni),
        "rapor_kodu_var": bool((rapor or {}).get("rapor_kodu")),
        "rapor_icd_sayisi": len((rapor or {}).get("icd_listesi") or []),
        "rapor_etken_madde_sayisi": len((rapor or {}).get("etken_madde_listesi") or []),
        "rapor_ek_bilgi_sayisi": len((rapor or {}).get("ek_bilgiler") or []),
        "rapor_doktor_brans_sayisi": len(
            (rapor or {}).get("rapor_doktor_uzmanliklari") or []),
        "hasta_yasi_var": bool(paket.get("hasta", {}).get("yas")),
        "hasta_cinsiyet_var": bool(paket.get("hasta", {}).get("cinsiyet")),
        "hasta_diger_rapor_sayisi": len(paket.get("hasta_diger_raporlari") or []),
        "hasta_diger_rapor_zenginlik": _gecmis_rapor_zenginlik_ozeti(
            paket.get("hasta_diger_raporlari") or []),
        "hasta_ilac_gecmisi_sayisi": len(paket.get("hasta_ilac_gecmisi") or []),
        "medula_rapor_sayisi": sum(
            1 for r in paket.get("hasta_diger_raporlari") or []
            if r.get("kaynak") == "medula"),
        "medula_ilac_sayisi": sum(
            1 for r in paket.get("hasta_ilac_gecmisi") or []
            if r.get("kaynak") == "medula"),
        "endikasyon_disi_izin_sayisi": len(
            paket.get("endikasyon_disi_izinler") or []),
        "recete_diger_ilac_sayisi": len(paket.get("recete_diger_ilaclari") or []),
        "uyari_sayisi": len(paket.get("uyarilar") or []),
    }


def _gecmis_rapor_zenginlik_ozeti(raporlar: List[Dict[str, Any]]) -> Dict[str, int]:
    """Geçmiş raporların toplu zenginleştirme istatistikleri (özet sayım)."""
    return {
        "toplam_icd": sum(len(r.get("icd_listesi") or []) for r in raporlar),
        "toplam_etken_madde": sum(
            len(r.get("etken_madde_listesi") or []) for r in raporlar),
        "toplam_ek_bilgi": sum(len(r.get("ek_bilgiler") or []) for r in raporlar),
        "toplam_doktor_brans": sum(
            len(r.get("rapor_doktor_uzmanliklari") or []) for r in raporlar),
        "toplam_rapor_kodu": sum(
            len(r.get("rapor_kodlari") or []) for r in raporlar),
        "metni_dolu_rapor": sum(
            1 for r in raporlar if (r.get("rapor_metni") or "").strip()),
    }


# ──────────────────────────────────────────────────────────────────────
# BÖLÜM OLUŞTURUCULAR
# ──────────────────────────────────────────────────────────────────────

def _recete_bolumu_olustur(s: Dict[str, Any]) -> Dict[str, Any]:
    """Tek reçete-ilaç satırından reçete bölümünü çıkar.

    Satır dict'i hem ham DB kolon adlarını (`RxEReceteNo`, `UrunAdi`)
    hem aylik_recete_sorgu_gui._satir_olustur'un normalize edilmiş kısa
    adlarını (`rec_no`, `ilac`, `atc`...) taşıyabilir. İkisini de dene.
    """
    return {
        "recete_no": str(
            s.get("RxEReceteNo") or s.get("e_recete_no")
            or s.get("rec_no") or ""),
        "recete_tarihi": _tarihi_iso(
            s.get("RxIslemTarihi") or s.get("RxKayitTarihi")
            or s.get("islem_tarihi") or s.get("rec_tar")),
        "recete_alt_turu": str(
            s.get("recete_alt_turu") or s.get("RxReceteAltTuruAdi")
            or s.get("rec_alttur") or ""),
        "recete_rengi": str(
            s.get("recete_rengi") or s.get("ReceteRenkAdi")
            or s.get("rec_tip") or ""),
        "provizyon_tipi": str(s.get("provizyon_tipi") or ""),
        "recete_teshis": str(
            s.get("recete_teshis") or s.get("teshis_tum")
            or s.get("rec_tesh") or ""),
        "recete_aciklama": str(
            s.get("recete_aciklama") or s.get("aciklama")
            or s.get("rec_ack") or ""),
        # Eczacının Medula kayıt sırasında manuel seçtiği uyarı kodları
        # (Idame Tedavi, Başlangıç Raporu vb.). Bunlar SUT şart kanıtı
        # değil, eczacının beyanı — AI'a bu netlikte sunulur.
        "uyari_kodlari": str(
            s.get("uyari_kodlari") or s.get("uyari") or ""),
        # NOT: 'medula_mesaji' alanı (Medula provizyon popup uyarıları,
        # RxUyarilari) AI paketinden ÇIKARILDI — bu mesajlar reçete tam
        # girilmediğinde fırlayan kayıt-zamanı uyarıları; SUT denetimi için
        # gürültü, AI'ı yanıltıyordu (2026-05-22 kullanıcı geri bildirimi).
        "ilac": {
            "urun_adi": str(
                s.get("UrunAdi") or s.get("urun_adi") or s.get("ilac_adi")
                or s.get("ilac") or ""),
            "atc_kodu": str(
                s.get("ATCKodu") or s.get("atc_kodu") or s.get("atc") or ""),
            "atc_aciklama": str(
                s.get("ATCTurkce") or s.get("atc_aciklama")
                or s.get("etkin") or ""),
            "adet": _safe_int(s.get("RIAdet") or s.get("adet") or s.get("kutu")),
            "doz": str(s.get("RIDoz") or s.get("doz") or s.get("rec_doz") or ""),
            "tekrar": _safe_int(s.get("RITekrar") or s.get("tekrar")),
            "aralik": _safe_int(s.get("RIAralik") or s.get("aralik")),
            "periyot": str(s.get("RIPeriyotAdi") or s.get("periyot") or ""),
            "toplam_kutu": _safe_int(s.get("RIToplam") or s.get("toplam")),
            "fiyat_farki": _safe_float(s.get("RIFiyatFarki") or s.get("fiyat_farki")),
            "esdeger_grubu": str(s.get("UrunEsdegerId") or s.get("esdeger") or ""),
            "sut_maddesi": str(s.get("sut") or s.get("sut_maddesi") or ""),
        },
        "doktor": {
            "brans": str(
                s.get("brans") or s.get("BransAdi") or s.get("DoktorBrans") or ""),
            "rapor_doktor_brans": str(
                s.get("RaporDoktorBrans") or s.get("rapor_doktor_brans") or ""),
            "tesis": str(
                s.get("hastane") or s.get("HastaneAdi")
                or s.get("tesis_kodu") or ""),
            "kurum": str(
                s.get("kurum") or s.get("KurumAdi") or s.get("kurum_adi") or ""),
        },
    }


def _hasta_bolumu_olustur(s: Dict[str, Any]) -> Dict[str, Any]:
    """Anonimleştirilmiş hasta bilgisi."""
    tc_raw = (s.get("MusteriTCKN") or s.get("hasta_tc")
              or s.get("tc") or "")
    dogum = (s.get("MusteriDogumTarihi") or s.get("dogum_tarihi")
             or s.get("hasta_dogum"))
    cinsiyet = (s.get("MusteriCinsiyet") or s.get("cinsiyet")
                or s.get("cins") or "")

    # Yaş — _satir_olustur 'yas' anahtarına yas_hesapla() sonucunu yazıyor;
    # önce o oku, yoksa doğum tarihinden hesapla.
    yas = s.get("yas")
    if yas is None or yas == "":
        yas = s.get("hasta_yasi")
    if yas is None or yas == "":
        yas = _yas_hesapla(dogum)
    else:
        try:
            yas = int(yas)
        except (ValueError, TypeError):
            yas = _yas_hesapla(dogum)

    return {
        "tc_hash": _tc_hash(tc_raw),    # tutarlılık için, ham TC YOK
        "yas": yas,
        "cinsiyet": _cinsiyet_normalize(cinsiyet),
        "kapsam": str(
            s.get("kapsam") or s.get("KapsamAdi") or s.get("hasta_tip") or ""),
        "emeklilik": str(s.get("emeklilik") or s.get("MusteriEmeklilik") or ""),
    }


def _rapor_bolumu_olustur(s: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reçeteye bağlı rapor (varsa)."""
    rapor_no = (s.get("RaporAnaRaporNo") or s.get("RIRaporNo")
                or s.get("rapor_no") or s.get("rap_tak_no") or "")
    # Rapor açıklama metni — _satir_olustur 'rap_ack' anahtarına " | " ile
    # birleştirilmiş açıklamaları yazıyor. Ham RaporAnaAciklamalar varsa onu
    # tercih et, yoksa rap_ack'i kullan.
    rapor_aciklama = (s.get("RaporAnaAciklamalar") or s.get("rapor_aciklama")
                       or s.get("rapor_tum_metin") or s.get("rap_ack") or "")
    rapor_kodu = (s.get("sr_rapor_kodu") or s.get("rapor_kodu")
                   or s.get("rap_kod") or s.get("RIRaporKodId") or "")
    rapor_teshis = (s.get("rapor_teshis") or s.get("teshis_rapor")
                     or s.get("rap_tesh") or "")
    # Hiçbir rapor sinyali yoksa null döndür
    if not (rapor_no or rapor_aciklama or rapor_kodu or rapor_teshis):
        return None
    return {
        "rapor_no": str(rapor_no),
        "rapor_takip_no": str(s.get("rap_tak_no") or ""),
        "rapor_tarihi": _tarihi_iso(
            s.get("RaporAnaRaporTarihi") or s.get("rapor_tarihi")),
        "rapor_kodu": str(rapor_kodu),
        "rapor_kodu_aciklama": str(s.get("rap_kod_aciklama") or ""),
        "rapor_metni": str(rapor_aciklama)[:8000],   # 8K char limit
        "rapor_secim_kaynagi": str(s.get("rapor_secim_kaynagi") or ""),
        "rapor_teshis": str(rapor_teshis),
        "rapor_dozu": str(s.get("rap_doz") or ""),
    }


# ──────────────────────────────────────────────────────────────────────
# BOTANIK DB EK VERİ — hasta geçmişi
# ──────────────────────────────────────────────────────────────────────

def _botanik_db_ek_veri(
    satir: Dict[str, Any],
    cfg: PaketKonfig,
    db: Any = None,
) -> Dict[str, Any]:
    """Botanik DB'den ek sorgular:
        • Hasta'nın diğer raporları (son N yıl)
        • Hasta'nın ilaç geçmişi (son N ay)
        • Bu reçetenin diğer ilaçları (aynı RxId)
        • Aktif raporun zenginleştirme verisi (ICD'ler, etken madde, ek bilgi)
    """
    sonuc: Dict[str, Any] = {
        "hasta_diger_raporlari": [],
        "hasta_ilac_gecmisi": [],
        "recete_diger_ilaclari": [],
        "rapor_detay": {},
        "uyarilar": [],
    }

    musteri_id = (satir.get("RxMusteriId") or satir.get("MusteriId")
                  or satir.get("musteri_id"))
    rx_id = satir.get("RxId") or satir.get("rx_id")
    ri_id = satir.get("RIId") or satir.get("ri_id")
    rapor_ana_id = satir.get("RaporAnaId") or satir.get("rapor_ana_id")
    if not musteri_id and not rx_id:
        sonuc["uyarilar"].append({
            "kaynak": "botanik_db",
            "not": "MusteriId/RxId yok — ek sorgular atlandı",
        })
        return sonuc

    _db = db
    _db_acildi = False
    if _db is None:
        try:
            from botanik_db import BotanikDB
            _db = BotanikDB()
            if not _db.baglan():
                raise RuntimeError("Botanik DB bağlantısı kurulamadı")
            _db_acildi = True
        except Exception as e:
            sonuc["uyarilar"].append({
                "kaynak": "botanik_db",
                "hata": f"Bağlantı: {e}",
            })
            return sonuc

    try:
        if musteri_id:
            sonuc["hasta_diger_raporlari"] = _hasta_raporlari_sorgula(
                _db, musteri_id, cfg.rapor_gecmisi_yil,
            )
            sonuc["hasta_ilac_gecmisi"] = _hasta_ilac_gecmisi_sorgula(
                _db, musteri_id, cfg.ilac_gecmisi_ay,
                hariç_rx_id=rx_id,
                max_kayit=cfg.max_hasta_ilac,
            )
        if rx_id:
            sonuc["recete_diger_ilaclari"] = _recete_diger_ilaclari_sorgula(
                _db, rx_id, hariç_ri_id=ri_id, max_kayit=cfg.max_recete_ilac,
            )
        if rapor_ana_id:
            sonuc["rapor_detay"] = _rapor_zenginlestir(_db, rapor_ana_id)
    finally:
        if _db_acildi:
            try:
                _db.kapat()
            except Exception:
                pass

    return sonuc


def _rapor_zenginlestir(db: Any, rapor_ana_id: Any) -> Dict[str, Any]:
    """Aktif rapor için ek tablolar — ICD'ler, etken maddeler, ek bilgi.

    Mevcut SUT kontrolünün kullandığı aynı tablolar:
        • RaporRaporKodlariICD + ICD     → çoklu teşhis kodları
        • RaporEtkinMadde + EtkinMadde  → etken madde + doz + miktar + tekrar
        • RaporEkBilgi                   → ek açıklamalar (REBTuru/REBDeger/REBAciklama)
    """
    detay: Dict[str, Any] = {
        "icd_listesi": [],
        "etken_madde_listesi": [],
        "ek_bilgiler": [],
        "rapor_doktor_uzmanliklari": [],
    }

    # 1) ICD'ler — bir raporun 5'e kadar tanı kodu olabilir
    try:
        rows = db.sorgu_calistir(
            """SELECT icd1.ICDKodu AS K1, icd1.ICDAciklamasi AS A1,
                      icd2.ICDKodu AS K2, icd2.ICDAciklamasi AS A2,
                      icd3.ICDKodu AS K3, icd3.ICDAciklamasi AS A3,
                      icd4.ICDKodu AS K4, icd4.ICDAciklamasi AS A4,
                      icd5.ICDKodu AS K5, icd5.ICDAciklamasi AS A5
               FROM RaporRaporKodlariICD rrki
               LEFT JOIN ICD icd1 ON icd1.ICDId = rrki.RRKIICDId
               LEFT JOIN ICD icd2 ON icd2.ICDId = rrki.RRKIICDId2
               LEFT JOIN ICD icd3 ON icd3.ICDId = rrki.RRKIICDId3
               LEFT JOIN ICD icd4 ON icd4.ICDId = rrki.RRKIICDId4
               LEFT JOIN ICD icd5 ON icd5.ICDId = rrki.RRKIICDId5
               WHERE rrki.RRKIRaporAnaId = ?
                 AND (rrki.RRKISilme IS NULL OR rrki.RRKISilme = 0)""",
            (rapor_ana_id,),
        )
        for r in rows or []:
            for n in (1, 2, 3, 4, 5):
                kod = (r.get(f"K{n}") or "").strip()
                ack = (r.get(f"A{n}") or "").strip()
                if kod:
                    detay["icd_listesi"].append({
                        "icd_kodu": kod,
                        "aciklama": ack,
                    })
    except Exception as e:
        logger.warning("rapor ICD sorgu fail: %s", e)

    # 2) Etken Madde + doz
    try:
        rows = db.sorgu_calistir(
            """SELECT em.EtkinMaddeId,
                      ekm.EtkinMaddeKodu AS etken_kodu,
                      ekm.EtkinMaddeAdi  AS etken_adi,
                      em.EtkinMaddeDoz   AS doz,
                      em.EtkinMaddeAdetMiktar AS adet_miktar,
                      em.EtkinMaddeTekrar AS tekrar,
                      em.EtkinMaddeAralik AS aralik,
                      em.EtkinMaddePeriyotId AS periyot_id,
                      p.PeriyotAdi AS periyot_adi
               FROM RaporEtkinMadde em
               LEFT JOIN EtkinMadde ekm ON ekm.EtkinMaddeId = em.EtkinMaddeId
               LEFT JOIN Periyot p ON p.PeriyotId = em.EtkinMaddePeriyotId
               WHERE em.EtkinMaddeRaporAnaId = ?
                 AND (em.EtkinMaddeSilme IS NULL OR em.EtkinMaddeSilme = 0)""",
            (rapor_ana_id,),
        )
        for r in rows or []:
            detay["etken_madde_listesi"].append({
                "etken_kodu": str(r.get("etken_kodu") or ""),
                "etken_adi": str(r.get("etken_adi") or ""),
                "doz": str(r.get("doz") or ""),
                "adet_miktar": _safe_int(r.get("adet_miktar")),
                "tekrar": _safe_int(r.get("tekrar")),
                "aralik": _safe_int(r.get("aralik")),
                "periyot": str(r.get("periyot_adi") or ""),
            })
    except Exception as e:
        logger.warning("RaporEtkinMadde sorgu fail: %s", e)

    # 3) Ek bilgiler — rapor metni dışında yapılandırılmış ek alanlar
    try:
        rows = db.sorgu_calistir(
            """SELECT REBTuru AS turu, REBDeger AS deger, REBAciklama AS aciklama
               FROM RaporEkBilgi
               WHERE REBRaporAnaId = ?""",
            (rapor_ana_id,),
        )
        for r in rows or []:
            detay["ek_bilgiler"].append({
                "turu": str(r.get("turu") or ""),
                "deger": str(r.get("deger") or ""),
                "aciklama": str(r.get("aciklama") or ""),
            })
    except Exception as e:
        logger.warning("RaporEkBilgi sorgu fail: %s", e)

    # 4) Rapor doktorlarının uzmanlıkları (sağlık kurulu raporu olabilir)
    try:
        rows = db.sorgu_calistir(
            """SELECT b.BransAdi AS brans
               FROM RaporDoktor rd
               LEFT JOIN Brans b ON b.BransId = rd.RaporDoktorBransId
               WHERE rd.RaporDoktorRaporAnaId = ?
                 AND (rd.RaporDoktorSilme IS NULL OR rd.RaporDoktorSilme = 0)""",
            (rapor_ana_id,),
        )
        for r in rows or []:
            br = (r.get("brans") or "").strip()
            if br:
                detay["rapor_doktor_uzmanliklari"].append(br)
    except Exception as e:
        logger.warning("RaporDoktor sorgu fail: %s", e)

    return detay


def _hasta_raporlari_sorgula(db: Any, musteri_id: Any, yil: int) -> List[Dict[str, Any]]:
    """Hasta'nın son N yıl içindeki raporlarını döndür.

    Her rapor için zenginleştirme dahil:
      • temel: rapor_no, rapor_takip_no, rapor_tarihi, rapor_metni
      • icd_listesi (5'e kadar tanı)
      • etken_madde_listesi (doz+miktar+tekrar)
      • ek_bilgiler (REBTuru/Deger/Aciklama)
      • rapor_doktor_uzmanliklari (sağlık kurulu için)

    Performans: önce TOP 50 raporu çek; sonra ID listesini toplu IN clause ile
    4 ek sorgu yap (N+1 değil). Toplam ~5 sorgu.
    """
    sql = """
        SELECT TOP 50
            ra.RaporAnaId,
            CAST(ra.RaporAnaRaporNo AS NVARCHAR(50)) AS rapor_no,
            CAST(ra.RaporAnaRaporTakipNo AS NVARCHAR(50)) AS rapor_takip_no,
            ra.RaporAnaRaporTarihi AS rapor_tarihi,
            ra.RaporAnaAciklamalar AS rapor_metni
        FROM RaporAna ra
        WHERE ra.RaporAnaMusteriId = ?
          AND (ra.RaporAnaSilme IS NULL OR ra.RaporAnaSilme = 0)
          AND ra.RaporAnaRaporTarihi >= DATEADD(YEAR, -?, GETDATE())
        ORDER BY ra.RaporAnaRaporTarihi DESC
    """
    try:
        rows = db.sorgu_calistir(sql, (musteri_id, int(yil)))
    except Exception as e:
        logger.warning("hasta_raporlari sorgusu fail: %s", e)
        return []

    cikti: List[Dict[str, Any]] = []
    rapor_ana_idler: List[Any] = []
    for r in rows or []:
        rid = r.get("RaporAnaId")
        cikti.append({
            "rapor_ana_id": rid,
            "rapor_no": str(r.get("rapor_no") or ""),
            "rapor_takip_no": str(r.get("rapor_takip_no") or ""),
            "rapor_tarihi": _tarihi_iso(r.get("rapor_tarihi")),
            "rapor_metni": (str(r.get("rapor_metni") or ""))[:4000],
            "icd_listesi": [],
            "etken_madde_listesi": [],
            "ek_bilgiler": [],
            "rapor_doktor_uzmanliklari": [],
            "rapor_kodlari": [],
        })
        if rid:
            rapor_ana_idler.append(rid)

    if rapor_ana_idler:
        zenginlik = _raporlar_toplu_zenginlestir(db, rapor_ana_idler)
        for kayit in cikti:
            rid = kayit.pop("rapor_ana_id", None)
            ez = zenginlik.get(rid)
            if ez:
                kayit["icd_listesi"] = ez.get("icd_listesi", [])
                kayit["etken_madde_listesi"] = ez.get("etken_madde_listesi", [])
                kayit["ek_bilgiler"] = ez.get("ek_bilgiler", [])
                kayit["rapor_doktor_uzmanliklari"] = ez.get(
                    "rapor_doktor_uzmanliklari", [])
                kayit["rapor_kodlari"] = ez.get("rapor_kodlari", [])

    return cikti


def _raporlar_toplu_zenginlestir(
    db: Any, rapor_ana_idler: List[Any],
) -> Dict[Any, Dict[str, Any]]:
    """Birden fazla rapor için ICD/etken madde/ek bilgi/doktor branş + rapor
    kodlarını toplu çek (tek IN sorgusuyla).

    Returns: {rapor_ana_id: {icd_listesi, etken_madde_listesi, ek_bilgiler,
                              rapor_doktor_uzmanliklari, rapor_kodlari}}
    """
    sonuc: Dict[Any, Dict[str, Any]] = {}
    for rid in rapor_ana_idler:
        sonuc[rid] = {
            "icd_listesi": [],
            "etken_madde_listesi": [],
            "ek_bilgiler": [],
            "rapor_doktor_uzmanliklari": [],
            "rapor_kodlari": [],
        }

    # 1000'lik chunk'lar (SQL Server IN clause limiti güvenli)
    def _chunklar(liste, boyut=1000):
        for i in range(0, len(liste), boyut):
            yield liste[i:i + boyut]

    # ──────── 1) ICD'ler (5 slot per rapor) ────────
    for chunk in _chunklar(rapor_ana_idler):
        ph = ",".join("?" * len(chunk))
        try:
            rows = db.sorgu_calistir(
                f"""SELECT rrki.RRKIRaporAnaId AS rid,
                           icd1.ICDKodu AS K1, icd1.ICDAciklamasi AS A1,
                           icd2.ICDKodu AS K2, icd2.ICDAciklamasi AS A2,
                           icd3.ICDKodu AS K3, icd3.ICDAciklamasi AS A3,
                           icd4.ICDKodu AS K4, icd4.ICDAciklamasi AS A4,
                           icd5.ICDKodu AS K5, icd5.ICDAciklamasi AS A5
                    FROM RaporRaporKodlariICD rrki
                    LEFT JOIN ICD icd1 ON icd1.ICDId = rrki.RRKIICDId
                    LEFT JOIN ICD icd2 ON icd2.ICDId = rrki.RRKIICDId2
                    LEFT JOIN ICD icd3 ON icd3.ICDId = rrki.RRKIICDId3
                    LEFT JOIN ICD icd4 ON icd4.ICDId = rrki.RRKIICDId4
                    LEFT JOIN ICD icd5 ON icd5.ICDId = rrki.RRKIICDId5
                    WHERE rrki.RRKIRaporAnaId IN ({ph})
                      AND (rrki.RRKISilme IS NULL OR rrki.RRKISilme = 0)""",
                tuple(chunk),
            )
            for r in rows or []:
                rid = r.get("rid")
                if rid not in sonuc:
                    continue
                for n in (1, 2, 3, 4, 5):
                    kod = (r.get(f"K{n}") or "").strip()
                    ack = (r.get(f"A{n}") or "").strip()
                    if kod:
                        sonuc[rid]["icd_listesi"].append({
                            "icd_kodu": kod, "aciklama": ack,
                        })
        except Exception as e:
            logger.warning("hasta_raporlari ICD toplu sorgu fail: %s", e)

    # ──────── 2) Rapor kodları (RaporKodlari üzerinden — RRKIRaporKodId) ────────
    for chunk in _chunklar(rapor_ana_idler):
        ph = ",".join("?" * len(chunk))
        try:
            rows = db.sorgu_calistir(
                f"""SELECT rrki.RRKIRaporAnaId AS rid,
                           rk.RaporKodu AS kod,
                           rk.RaporKodAciklama AS aciklama
                    FROM RaporRaporKodlariICD rrki
                    LEFT JOIN RaporKodlari rk ON rk.RaporKodId = rrki.RRKIRaporKodId
                    WHERE rrki.RRKIRaporAnaId IN ({ph})
                      AND (rrki.RRKISilme IS NULL OR rrki.RRKISilme = 0)
                      AND rk.RaporKodId IS NOT NULL""",
                tuple(chunk),
            )
            for r in rows or []:
                rid = r.get("rid")
                if rid not in sonuc:
                    continue
                kod = (r.get("kod") or "").strip()
                if kod:
                    sonuc[rid]["rapor_kodlari"].append({
                        "kod": kod,
                        "aciklama": (r.get("aciklama") or "").strip(),
                    })
        except Exception as e:
            logger.warning("hasta_raporlari rapor_kodlari sorgu fail: %s", e)

    # ──────── 3) Etken madde + doz ────────
    for chunk in _chunklar(rapor_ana_idler):
        ph = ",".join("?" * len(chunk))
        try:
            rows = db.sorgu_calistir(
                f"""SELECT em.EtkinMaddeRaporAnaId AS rid,
                           ekm.EtkinMaddeKodu AS etken_kodu,
                           ekm.EtkinMaddeAdi  AS etken_adi,
                           em.EtkinMaddeDoz AS doz,
                           em.EtkinMaddeAdetMiktar AS adet_miktar,
                           em.EtkinMaddeTekrar AS tekrar,
                           em.EtkinMaddeAralik AS aralik,
                           p.PeriyotAdi AS periyot_adi
                    FROM RaporEtkinMadde em
                    LEFT JOIN EtkinMadde ekm ON ekm.EtkinMaddeId = em.EtkinMaddeId
                    LEFT JOIN Periyot p ON p.PeriyotId = em.EtkinMaddePeriyotId
                    WHERE em.EtkinMaddeRaporAnaId IN ({ph})
                      AND (em.EtkinMaddeSilme IS NULL OR em.EtkinMaddeSilme = 0)""",
                tuple(chunk),
            )
            for r in rows or []:
                rid = r.get("rid")
                if rid not in sonuc:
                    continue
                sonuc[rid]["etken_madde_listesi"].append({
                    "etken_kodu": str(r.get("etken_kodu") or ""),
                    "etken_adi": str(r.get("etken_adi") or ""),
                    "doz": str(r.get("doz") or ""),
                    "adet_miktar": _safe_int(r.get("adet_miktar")),
                    "tekrar": _safe_int(r.get("tekrar")),
                    "aralik": _safe_int(r.get("aralik")),
                    "periyot": str(r.get("periyot_adi") or ""),
                })
        except Exception as e:
            logger.warning("hasta_raporlari etken_madde sorgu fail: %s", e)

    # ──────── 4) Ek bilgiler ────────
    for chunk in _chunklar(rapor_ana_idler):
        ph = ",".join("?" * len(chunk))
        try:
            rows = db.sorgu_calistir(
                f"""SELECT REBRaporAnaId AS rid,
                           REBTuru AS turu, REBDeger AS deger,
                           REBAciklama AS aciklama
                    FROM RaporEkBilgi
                    WHERE REBRaporAnaId IN ({ph})""",
                tuple(chunk),
            )
            for r in rows or []:
                rid = r.get("rid")
                if rid not in sonuc:
                    continue
                sonuc[rid]["ek_bilgiler"].append({
                    "turu": str(r.get("turu") or ""),
                    "deger": str(r.get("deger") or ""),
                    "aciklama": str(r.get("aciklama") or ""),
                })
        except Exception as e:
            logger.warning("hasta_raporlari ek_bilgi sorgu fail: %s", e)

    # ──────── 5) Doktor branşları ────────
    for chunk in _chunklar(rapor_ana_idler):
        ph = ",".join("?" * len(chunk))
        try:
            rows = db.sorgu_calistir(
                f"""SELECT rd.RaporDoktorRaporAnaId AS rid,
                           b.BransAdi AS brans
                    FROM RaporDoktor rd
                    LEFT JOIN Brans b ON b.BransId = rd.RaporDoktorBransId
                    WHERE rd.RaporDoktorRaporAnaId IN ({ph})
                      AND (rd.RaporDoktorSilme IS NULL OR rd.RaporDoktorSilme = 0)""",
                tuple(chunk),
            )
            for r in rows or []:
                rid = r.get("rid")
                if rid not in sonuc:
                    continue
                br = (r.get("brans") or "").strip()
                if br:
                    sonuc[rid]["rapor_doktor_uzmanliklari"].append(br)
        except Exception as e:
            logger.warning("hasta_raporlari doktor sorgu fail: %s", e)

    return sonuc


def _hasta_ilac_gecmisi_sorgula(
    db: Any,
    musteri_id: Any,
    ay: int,
    hariç_rx_id: Any = None,
    max_kayit: int = 100,
) -> List[Dict[str, Any]]:
    """Hasta'nın son N ay içinde aldığı ilaçları döndür (bu reçete hariç)."""
    sql = f"""
        SELECT TOP {int(max_kayit)}
            ra.RxIslemTarihi AS recete_tarihi,
            u.UrunAdi AS urun_adi,
            atc.ATCKodu AS atc_kodu,
            atc.ATCTurkce AS atc_aciklama,
            ri.RIAdet AS adet,
            ri.RIDoz AS doz,
            ri.RIToplam AS toplam_kutu
        FROM ReceteIlaclari ri
        INNER JOIN ReceteAna ra ON ra.RxId = ri.RIRxId
        LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
        LEFT JOIN ATC atc ON atc.ATCId = u.UrunATCId
        WHERE ra.RxMusteriId = ?
          AND (ri.RISilme IS NULL OR ri.RISilme = 0)
          AND ra.RxIslemTarihi >= DATEADD(MONTH, -?, GETDATE())
          { 'AND ra.RxId <> ?' if hariç_rx_id else '' }
        ORDER BY ra.RxIslemTarihi DESC
    """
    params: tuple = (musteri_id, int(ay))
    if hariç_rx_id:
        params = (musteri_id, int(ay), hariç_rx_id)
    try:
        rows = db.sorgu_calistir(sql, params)
    except Exception as e:
        logger.warning("hasta_ilac_gecmisi sorgusu fail: %s", e)
        return []
    cikti: List[Dict[str, Any]] = []
    for r in rows or []:
        cikti.append({
            "tarih": _tarihi_iso(r.get("recete_tarihi")),
            "urun_adi": str(r.get("urun_adi") or ""),
            "atc_kodu": str(r.get("atc_kodu") or ""),
            "atc_aciklama": str(r.get("atc_aciklama") or ""),
            "adet": _safe_int(r.get("adet")),
            "doz": str(r.get("doz") or ""),
            "toplam_kutu": _safe_int(r.get("toplam_kutu")),
        })
    return cikti


def _recete_diger_ilaclari_sorgula(
    db: Any,
    rx_id: Any,
    hariç_ri_id: Any = None,
    max_kayit: int = 50,
) -> List[Dict[str, Any]]:
    """Aynı reçetedeki diğer ilaçları döndür (eş-zamanlı yazılmış)."""
    sql = f"""
        SELECT TOP {int(max_kayit)}
            ri.RIId AS ri_id,
            u.UrunAdi AS urun_adi,
            atc.ATCKodu AS atc_kodu,
            atc.ATCTurkce AS atc_aciklama,
            ri.RIAdet AS adet,
            ri.RIDoz AS doz,
            ri.RIToplam AS toplam_kutu,
            ri.RIRaporNo AS rapor_no
        FROM ReceteIlaclari ri
        LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
        LEFT JOIN ATC atc ON atc.ATCId = u.UrunATCId
        WHERE ri.RIRxId = ?
          AND (ri.RISilme IS NULL OR ri.RISilme = 0)
          { 'AND ri.RIId <> ?' if hariç_ri_id else '' }
    """
    params: tuple = (rx_id,)
    if hariç_ri_id:
        params = (rx_id, hariç_ri_id)
    try:
        rows = db.sorgu_calistir(sql, params)
    except Exception as e:
        logger.warning("recete_diger_ilaclari sorgusu fail: %s", e)
        return []
    cikti: List[Dict[str, Any]] = []
    for r in rows or []:
        cikti.append({
            "urun_adi": str(r.get("urun_adi") or ""),
            "atc_kodu": str(r.get("atc_kodu") or ""),
            "atc_aciklama": str(r.get("atc_aciklama") or ""),
            "adet": _safe_int(r.get("adet")),
            "doz": str(r.get("doz") or ""),
            "toplam_kutu": _safe_int(r.get("toplam_kutu")),
            "rapor_no": str(r.get("rapor_no") or ""),
        })
    return cikti


# ──────────────────────────────────────────────────────────────────────
# YARDIMCI
# ──────────────────────────────────────────────────────────────────────

def _safe_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
