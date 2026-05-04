"""
SUT Kural Eşleştirici
Botanik ürün ID → kontrol_kurallari.db'deki etken madde kuralı zinciri.

Zincir (ATC üzerinden — SGKKodlari boş olduğu için):
  Urun.UrunATCId  →  ATC.ATCTurkce (örn "ATORVASTATİN")
    → normalize (TR karakter + uppercase)
    → kontrol_kurallari.etkin_madde_kurallari.etkin_madde prefix/eşit match

Bu modül cache mantığıyla çalışır: ilk açılışta tüm haritayı yükler,
sonra in-memory dict'lerden cevaplar.
"""

import logging
import os
import re
import sqlite3
from typing import Dict, List, Optional

from botanik_db import BotanikDB

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_KONTROL_KURAL_YOLU = os.path.join(_SCRIPT_DIR, "kontrol_kurallari.db")

# Türkçe karakter normalize tablosu
_TR_TRANS = str.maketrans("İıÖöÜüÇçŞşĞğ", "IiOoUuCcSsGg")


def _norm(s: str) -> str:
    """TR karakterleri ASCII'ye çevir, uppercase, strip."""
    return (s or "").translate(_TR_TRANS).upper().strip()


class SUTKuralEslestirici:
    """
    Ürün ID → SUT kuralı eşleştirme. Cache'li.

    Kullanım:
        e = SUTKuralEslestirici()
        e.yukle()
        kural = e.urun_kurali(urun_id=6546)
        # kural -> dict: etken_madde, sut_maddesi, rapor_kodu, aciklama, ...

        gruplar = e.sut_madde_listesi()  # dropdown için
    """

    def __init__(self, botanik_db: Optional[BotanikDB] = None):
        self.botanik_db = botanik_db
        # ATC bazlı zincir
        self._atc_id_to_norm: Dict[int, str] = {}        # ATCId -> normalize ATCTurkce
        self._urun_id_to_atc_norm: Dict[int, str] = {}   # UrunId -> normalize ATC adı
        self._kurallar: List[dict] = []                   # tüm kural satırları
        self._urun_id_to_kural: Dict[int, dict] = {}     # UrunId -> kural (önbellek)
        self._sut_madde_grupları: List[dict] = []
        self._yuklendi = False

    # ----------------------- yükleme -----------------------
    def yukle(self):
        """Tüm cache'leri doldur. Yeniden çağrılabilir."""
        try:
            self._atc_id_to_norm = self._atc_yukle()
            self._urun_id_to_atc_norm = self._urun_atc_yukle()
            self._kurallar = self._kontrol_kurallari_yukle()
            self._urun_id_to_kural = self._urun_kural_eslestirmesi_olustur()
            self._sut_madde_grupları = self._sut_madde_gruplarini_olustur()
            self._yuklendi = True
            logger.info(
                "SUT eşleştirici yüklendi: %d ATC, %d ürün ATC, %d kural, "
                "%d ürün-kural eşleşmesi, %d SUT grubu",
                len(self._atc_id_to_norm), len(self._urun_id_to_atc_norm),
                len(self._kurallar), len(self._urun_id_to_kural),
                len(self._sut_madde_grupları),
            )
        except Exception as e:
            logger.exception("Eşleştirici yükleme hatası: %s", e)

    def _atc_yukle(self) -> Dict[int, str]:
        """ATC.ATCId → normalize(ATCTurkce). Türkçe yoksa Original kullan."""
        if not self.botanik_db:
            return {}
        rows = self.botanik_db.sorgu_calistir(
            "SELECT ATCId, ATCTurkce, ATCOriginal FROM ATC"
        )
        return {
            r["ATCId"]: _norm(r["ATCTurkce"] or r["ATCOriginal"] or "")
            for r in rows if r.get("ATCTurkce") or r.get("ATCOriginal")
        }

    def _urun_atc_yukle(self) -> Dict[int, str]:
        """Urun.UrunId → normalize ATC adı"""
        if not self.botanik_db:
            return {}
        rows = self.botanik_db.sorgu_calistir(
            "SELECT UrunId, UrunATCId FROM Urun "
            "WHERE UrunSilme=0 AND UrunATCId IS NOT NULL AND UrunATCId > 0"
        )
        sonuc = {}
        for r in rows:
            atc_n = self._atc_id_to_norm.get(r["UrunATCId"])
            if atc_n:
                sonuc[r["UrunId"]] = atc_n
        return sonuc

    def _kontrol_kurallari_yukle(self) -> List[dict]:
        """Tüm aktif kuralları liste olarak yükle (norm_etkin_madde alanı eklenir)."""
        if not os.path.exists(_KONTROL_KURAL_YOLU):
            logger.warning("kontrol_kurallari.db bulunamadı: %s",
                            _KONTROL_KURAL_YOLU)
            return []
        try:
            with sqlite3.connect(_KONTROL_KURAL_YOLU) as c:
                c.row_factory = sqlite3.Row
                rows = c.execute("""
                    SELECT id, etkin_madde, sgk_kodu, sut_maddesi, rapor_kodu,
                           rapor_gerekli, raporlu_maks_doz, kontrol_tipi,
                           birlikte_yasaklar, aciklama
                    FROM etkin_madde_kurallari
                    WHERE aktif=1
                """).fetchall()
            sonuc = []
            for r in rows:
                d = dict(r)
                d["norm_etkin_madde"] = _norm(d.get("etkin_madde"))
                sonuc.append(d)
            return sonuc
        except Exception as e:
            logger.exception("kontrol_kurallari okuma hatası: %s", e)
            return []

    def _urun_kural_eslestirmesi_olustur(self) -> Dict[int, dict]:
        """
        UrunId → kural eşleşmesi (ATC adı vs etkin_madde fuzzy match).
        Strateji:
          1. Tam eşleşme (norm_atc == norm_etkin_madde)
          2. ATC adı kuralın etkin_madde'sinin başında geçiyor mu?
             (ör. "ATORVASTATIN" prefix of "ATORVASTATIN KALSIYUM")
          3. Kural etkin_madde'sinin ilk kelimesi ATC adında geçiyor mu?
        """
        sonuc = {}
        # Pre-index kuralları: norm → kural list
        norm_kurallar = {}
        for k in self._kurallar:
            norm_kurallar.setdefault(k["norm_etkin_madde"], []).append(k)

        for urun_id, atc_n in self._urun_id_to_atc_norm.items():
            if not atc_n:
                continue

            # 1) Tam eşleşme
            if atc_n in norm_kurallar:
                sonuc[urun_id] = norm_kurallar[atc_n][0]
                continue

            # 2) ATC adı bir kuralın etkin_madde'sinin başında
            best_match = None
            for k in self._kurallar:
                em = k["norm_etkin_madde"]
                if em.startswith(atc_n) or atc_n.startswith(em):
                    best_match = k
                    break
            if best_match:
                sonuc[urun_id] = best_match
                continue

            # 3) Kural ilk kelimesi ATC adında geçiyor mu? (riski yüksek, kombo)
            for k in self._kurallar:
                em_kelimeler = k["norm_etkin_madde"].split()
                if em_kelimeler and len(em_kelimeler[0]) >= 5:
                    if em_kelimeler[0] in atc_n:
                        sonuc[urun_id] = k
                        break

        return sonuc

    def _sut_madde_gruplarini_olustur(self) -> List[dict]:
        """Distinct sut_maddesi → grup adı + etken madde sayısı."""
        if not os.path.exists(_KONTROL_KURAL_YOLU):
            return []
        try:
            with sqlite3.connect(_KONTROL_KURAL_YOLU) as c:
                c.row_factory = sqlite3.Row
                rows = c.execute("""
                    SELECT sut_maddesi, COUNT(*) AS adet,
                           GROUP_CONCAT(etkin_madde, '|') AS maddeler,
                           GROUP_CONCAT(aciklama, '|') AS aciklamalar
                    FROM etkin_madde_kurallari
                    WHERE aktif=1
                      AND sut_maddesi IS NOT NULL AND sut_maddesi != ''
                    GROUP BY sut_maddesi
                    ORDER BY sut_maddesi
                """).fetchall()
            sonuc = []
            for r in rows:
                sut = r["sut_maddesi"]
                # Açıklamadan kategori adını çıkart (ilk cümlenin başı)
                kategori = self._kategori_cikart(r["aciklamalar"] or "")
                etkin_listesi = (r["maddeler"] or "").split("|")
                sonuc.append({
                    "sut_maddesi": sut,
                    "kategori": kategori,
                    "etkin_madde_sayisi": r["adet"],
                    "etkin_maddeler": etkin_listesi,
                })
            return sonuc
        except Exception as e:
            logger.exception("Grup oluşturma hatası: %s", e)
            return []

    def _kategori_cikart(self, aciklamalar: str) -> str:
        """
        Açıklama metnindeki ilk virgül/nokta öncesi kelimeleri kategori
        olarak alır. Aynı SUT'ta birden fazla satır varsa ilk dolu olanı
        kullanır.
        """
        if not aciklamalar:
            return "Diğer"
        parcalar = aciklamalar.split("|")
        for p in parcalar:
            p = (p or "").strip()
            if not p:
                continue
            # İlk noktaya veya iki noktaya kadar olan kısım
            m = re.match(r"^([^.:]+?)\s*[.:]", p)
            if m:
                kat = m.group(1).strip()
                # "Statin" değil "Statin." istemiyoruz
                kat = re.sub(r"\s*SUT\s*\d.*$", "", kat).strip()
                if kat and len(kat) <= 50:
                    return kat
        # Hiçbir şey bulunamadıysa
        return "Diğer"

    # ----------------------- sorgu API -----------------------
    def urun_kurali(self, urun_id: int) -> Optional[dict]:
        """Bir ürün ID'si için SUT kuralını döner. None ise eşleşme yok."""
        return self._urun_id_to_kural.get(urun_id)

    def urun_sut_maddesi(self, urun_id: int) -> str:
        """Sadece sut_maddesi string'i. Boş string olabilir."""
        kural = self.urun_kurali(urun_id)
        return (kural or {}).get("sut_maddesi") or ""

    def sut_madde_listesi(self) -> List[dict]:
        """Dropdown için: [{sut_maddesi, kategori, etkin_madde_sayisi}]"""
        return list(self._sut_madde_grupları)

    def sut_maddesinde_urunler(self, sut_maddesi: str) -> List[int]:
        """Bir SUT maddesi için ürün ID listesi (filtre kullanımı)."""
        return [
            urun_id for urun_id, kural in self._urun_id_to_kural.items()
            if kural.get("sut_maddesi") == sut_maddesi
        ]

    @property
    def yuklendi(self) -> bool:
        return self._yuklendi
