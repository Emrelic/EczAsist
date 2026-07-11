# -*- coding: utf-8 -*-
"""
E-Reçete Çözücü — Karakter Karışma Tablosu (DERECELİ ÇİFT yapısı)

Doktorların okunmaz el yazısında karışan karakterler artık **sıralı ağırlıklı
ÇİFTLER** olarak tutulur (eski "klik/grup" yapısı değil). Liste sırası = deneme
önceliği: 1. çift en sık, son çift en nadir. Bell Labs araştırması (l/1, O/0,
Z/2, 1/7 = hataların %50+'si) + el yazısı literatürü + kullanıcı derecelendirmesi
ile oluşturuldu.

Her çift: (a, b, derece). Rank = listedeki sıra (1-based). Üretim bu rank'e göre
önceliklendirilir (önce düşük rank'li tekli değişimler, sonra ikili).

Kullanım:
    t = KarismaTablosu()
    t.genislet("O")            -> ['O','0','D','Q','A']  (rank sırası)
    t.alternatifler_sirali("O")-> [('0',1),('D',17),('A',20),('Q',30)]
Ayar penceresinden çift ekle/sil/taşı ile düzenlenebilir. Yerel JSON.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_DIZIN = os.path.dirname(os.path.abspath(__file__))
KARISMA_JSON = os.path.join(_DIZIN, "erecete_karisma_tablosu.json")

# Geçerli e-reçete karakter seti (büyük harf + rakam).
VARSAYILAN_KARAKTER_SETI = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ── Varsayılan DERECELİ ÇİFT listesi (kullanıcı onaylı sıra, 1→31) ─────────
# (a, b, derece). Liste sırası = deneme önceliği. Tümü büyük harf/rakam
# (kod büyük harfe normalize edilir; küçük l/i/o/... büyük karşılıklarıdır).
VARSAYILAN_CIFTLER = [
    # Derece 1 — en sık (Bell Labs %50+ çekirdeği)
    ("0", "O", 1), ("1", "L", 1), ("1", "I", 1), ("I", "L", 1),
    # Derece 2 — sık (kavisli/ilmekli)
    ("5", "S", 2), ("2", "Z", 2), ("8", "B", 2), ("6", "G", 2), ("U", "V", 2),
    # Derece 3 — orta (el yazısı)
    ("1", "7", 3), ("7", "T", 3), ("I", "T", 3), ("9", "G", 3), ("4", "A", 3),
    ("J", "I", 3), ("0", "D", 3), ("O", "D", 3),
    # Derece 4 — nadir
    ("7", "Y", 4), ("7", "Z", 4), ("O", "A", 4), ("P", "Q", 4), ("9", "Y", 4),
    ("X", "K", 4), ("K", "R", 4), ("E", "F", 4), ("F", "I", 4), ("A", "Q", 4),
    ("A", "H", 4), ("0", "Q", 4), ("O", "Q", 4), ("Q", "D", 4),
]


def _norm(ch: str) -> str:
    """Tek karakteri normalize et: büyük harf (ASCII). Türkçe İ/ı → I."""
    if not ch:
        return ""
    c = ch.strip()
    if not c:
        return ""
    c = c[0]
    # Türkçe noktalı/noktasız i → ASCII I
    if c in ("İ", "ı", "i"):
        return "I"
    return c.upper()


def parse_karakterler(metin: str):
    """Kullanıcı girdisini ayrıştırır: virgül/boşluk/bitişik fark etmez.
    Her karakter büyük harfe çevrilir, sıra korunarak tekilleştirilir."""
    if not metin:
        return []
    ayirici = set(", ;\t\n-/|.")
    sonuc = []
    for ch in metin:
        if ch in ayirici:
            continue
        u = _norm(ch)
        if u and u not in sonuc:
            sonuc.append(u)
    return sonuc


class KarismaTablosu:
    """Dereceli karışma çiftlerini yükler, rank-sıralı genişletme yapar,
    düzenler ve kaydeder."""

    def __init__(self, dosya: str = KARISMA_JSON):
        self.dosya = dosya
        self.ciftler = []            # list[(a, b, derece)]
        self.karakter_seti = VARSAYILAN_KARAKTER_SETI
        self.yukle()

    # ── Yükleme / kaydetme ────────────────────────────────────────────
    def yukle(self):
        if os.path.exists(self.dosya):
            try:
                with open(self.dosya, "r", encoding="utf-8") as f:
                    veri = json.load(f)
                ciftler = veri.get("ciftler")
                if ciftler:
                    self.ciftler = [
                        (_norm(c[0]), _norm(c[1]),
                         int(c[2]) if len(c) > 2 else 4)
                        for c in ciftler if len(c) >= 2
                    ]
                    self.karakter_seti = str(
                        veri.get("karakter_seti", VARSAYILAN_KARAKTER_SETI))
                    self._indeks_kur()
                    return
            except Exception as e:
                logger.warning(f"Karışma tablosu okunamadı, varsayılan: {e}")
        self.ciftler = list(VARSAYILAN_CIFTLER)
        self.karakter_seti = VARSAYILAN_KARAKTER_SETI
        self._indeks_kur()
        try:
            self.kaydet()
        except Exception:
            pass

    def kaydet(self):
        veri = {
            "ciftler": [[a, b, d] for (a, b, d) in self.ciftler],
            "karakter_seti": self.karakter_seti,
        }
        with open(self.dosya, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        self._indeks_kur()
        logger.info(f"Karışma tablosu kaydedildi ({len(self.ciftler)} çift)")

    # ── İndeks: karakter -> [(partner, rank)] rank artan ──────────────
    def _indeks_kur(self):
        self._komsu = {}   # char -> list[(partner, rank)]
        for i, (a, b, _d) in enumerate(self.ciftler):
            rank = i + 1
            if a and b:
                self._komsu.setdefault(a, []).append((b, rank))
                self._komsu.setdefault(b, []).append((a, rank))
        for ch, lst in self._komsu.items():
            lst.sort(key=lambda t: t[1])   # rank'e göre

    # ── Genişletme (rank sıralı) ──────────────────────────────────────
    def alternatifler_sirali(self, karakter: str):
        """Bir karakterin karışabileceği (partner, rank) listesi, rank artan,
        geçerli karakter setiyle sınırlı."""
        u = _norm(karakter)
        if not u:
            return []
        cs = self.karakter_seti
        sonuc = []
        gorulen = set()
        for partner, rank in self._komsu.get(u, []):
            if partner != u and partner in cs and partner not in gorulen:
                gorulen.add(partner)
                sonuc.append((partner, rank))
        return sonuc

    def genislet(self, karakter: str, kendini_dahil_et: bool = True):
        """Karakter + karışabildikleri (rank sırası). Belirsiz mod / benzet için."""
        u = _norm(karakter)
        if not u:
            return []
        sonuc = []
        if kendini_dahil_et and (u in self.karakter_seti or True):
            sonuc.append(u)
        for partner, _rank in self.alternatifler_sirali(u):
            if partner not in sonuc:
                sonuc.append(partner)
        return sonuc

    def genislet_metin(self, metin: str):
        cikti = []
        for ch in parse_karakterler(metin):
            for v in self.genislet(ch):
                if v not in cikti:
                    cikti.append(v)
        return cikti

    # ── Düzenleme (ayar penceresi) ────────────────────────────────────
    def cift_ekle(self, a: str, b: str, derece: int = 4):
        a2, b2 = _norm(a), _norm(b)
        if not a2 or not b2 or a2 == b2:
            raise ValueError("Geçerli, farklı iki karakter girin.")
        for (x, y, _d) in self.ciftler:
            if {x, y} == {a2, b2}:
                raise ValueError(f"{a2} ↔ {b2} çifti zaten var.")
        try:
            d = max(1, min(9, int(derece)))
        except Exception:
            d = 4
        self.ciftler.append((a2, b2, d))
        self._indeks_kur()
        return (a2, b2, d)

    def cift_sil(self, indeks: int):
        if 0 <= indeks < len(self.ciftler):
            self.ciftler.pop(indeks)
            self._indeks_kur()

    def cift_tasi(self, indeks: int, yon: int):
        """Çifti listede yukarı(-1)/aşağı(+1) taşı (önceliği değiştirir)."""
        j = indeks + yon
        if 0 <= indeks < len(self.ciftler) and 0 <= j < len(self.ciftler):
            self.ciftler[indeks], self.ciftler[j] = \
                self.ciftler[j], self.ciftler[indeks]
            self._indeks_kur()
            return j
        return indeks

    def varsayilana_don(self):
        self.ciftler = list(VARSAYILAN_CIFTLER)
        self.karakter_seti = VARSAYILAN_KARAKTER_SETI
        self._indeks_kur()


_ORNEK = None


def get_tablo() -> "KarismaTablosu":
    global _ORNEK
    if _ORNEK is None:
        _ORNEK = KarismaTablosu()
    return _ORNEK


if __name__ == "__main__":
    t = KarismaTablosu()
    print("Çift sayısı:", len(t.ciftler))
    for ornek in ["O", "0", "1", "I", "5", "7", "G", "Q"]:
        print(f"  {ornek} -> genislet {t.genislet(ornek)} | "
              f"sirali {t.alternatifler_sirali(ornek)}")
