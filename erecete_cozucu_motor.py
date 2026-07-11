# -*- coding: utf-8 -*-
"""
E-Reçete Çözücü — Kombinasyon Motoru (saf, Medula'dan bağımsız)

Her pozisyon (kutucuk) için bir aday-karakter listesi üretir, ardından tüm
kombinasyonları (kartezyen çarpım) kullanıcının yazdığı sırayla verir.

Pozisyon kuralları (kullanıcı isteği):
  1. KESİN karakter girilmişse  -> sadece o karakter denenir (sabit).
  2. Aksi halde OLASI kutusundaki karakterler denenir (virgül/boşluk/bitişik
     fark etmez; sıra korunur, tekilleştirilir).
  3. Her ikisi de boşsa (pozisyon şüpheli ama aday verilmemiş) -> TÜM karakter
     seti sırayla denenir.

İlk üretilen kombinasyon = her pozisyonun İLK adayı (kullanıcının en iyi
tahmini). Sonra en sağdaki pozisyon en hızlı değişerek ilerler.
"""

import itertools
import logging

from erecete_karisma_tablosu import (
    KarismaTablosu,
    parse_karakterler,
    VARSAYILAN_KARAKTER_SETI,
)

logger = logging.getLogger(__name__)


class Pozisyon:
    """Tek bir kutucuğun durumu (3 alan: kesin / benzet / olasi).

    - kesin  : emin olunan karakter (genelde toplu girişten dolar).
    - benzet : "neye benzediği". Karışma tablosuna göre genişletilir.
    - olasi  : elle dikte edilen adaylar (virgül/boşluk/bitişik).

    Öncelik: benzet veya olasi doluysa ONLAR kullanılır (kesin'i EZER) →
    (olasi listesi) ∪ (benzet genişletmesi). İkisi de boşsa kesin kullanılır.
    Üçü de boşsa → tüm karakter seti. Bu sayede toplu giriş tüm kutuları
    'kesin' doldurur; şüpheli pozisyona sadece benzet yazmak yeterlidir.
    """

    def __init__(self, kesin: str = "", benzet: str = "", olasi: str = "",
                 aktif: bool = True):
        self.kesin = (kesin or "").strip()
        self.benzet = (benzet or "").strip()
        self.olasi = (olasi or "").strip()
        self.aktif = aktif   # False ise bu pozisyon numaranın parçası değil

    def _birlesik_adaylar(self, karakter_seti: str, tablo=None):
        """olasi (elle) ∪ benzet-genişletme — sıra korunur, tekilleştirilir."""
        cand = []
        # 1) Elle dikte edilen adaylar (öncelikli sıra)
        for c in parse_karakterler(self.olasi):
            if c in karakter_seti and c not in cand:
                cand.append(c)
        # 2) Benzetme → karışma tablosundan genişletme
        if tablo is not None:
            for v in tablo.genislet_metin(self.benzet):
                if v in karakter_seti and v not in cand:
                    cand.append(v)
        else:
            # tablo yoksa benzet karakterlerini ham ekle
            for c in parse_karakterler(self.benzet):
                if c in karakter_seti and c not in cand:
                    cand.append(c)
        return cand

    def adaylar(self, karakter_seti: str, tablo=None):
        """Bu pozisyon için denenecek karakterleri sırayla döndürür.
        Öncelik: benzet/olasi (ezer) → kesin → tümü."""
        cand = self._birlesik_adaylar(karakter_seti, tablo)
        if cand:
            return cand
        kesin = parse_karakterler(self.kesin)
        if kesin:
            return [kesin[0]]
        return list(karakter_seti)

    def durum_ozeti(self, karakter_seti: str, tablo=None):
        """('KESİN'|'SEÇİLİ'|'TÜMÜ', aday_listesi) döndürür — UI/özet için."""
        cand = self._birlesik_adaylar(karakter_seti, tablo)
        if cand:
            return "SEÇİLİ", cand
        kesin = parse_karakterler(self.kesin)
        if kesin:
            return "KESİN", [kesin[0]]
        return "TÜMÜ", list(karakter_seti)


class CozucuMotor:
    def __init__(self, tablo: KarismaTablosu = None):
        self.tablo = tablo or KarismaTablosu()

    @property
    def karakter_seti(self):
        return self.tablo.karakter_seti or VARSAYILAN_KARAKTER_SETI

    def pozisyon_adaylari(self, pozisyonlar):
        """Aktif pozisyonların aday listelerini döndürür (list[list[str]])."""
        ks = self.karakter_seti
        return [p.adaylar(ks, self.tablo) for p in pozisyonlar if p.aktif]

    def toplam_kombinasyon(self, pozisyonlar) -> int:
        toplam = 1
        for adaylar in self.pozisyon_adaylari(pozisyonlar):
            toplam *= max(1, len(adaylar))
        return toplam

    def kombinasyonlar(self, pozisyonlar):
        """Tüm kombinasyonları üreten generator (string döndürür).

        itertools.product en sağdaki pozisyonu en hızlı değiştirir; her aday
        listesinin ilk elemanı kullanıcının birincil tahmini olduğundan ilk
        üretilen değer = tüm birincil tahminlerin birleşimi.
        """
        aday_listeleri = self.pozisyon_adaylari(pozisyonlar)
        if not aday_listeleri:
            return
        for combo in itertools.product(*aday_listeleri):
            yield "".join(combo)

    # ── Eksik karakter modu ───────────────────────────────────────────
    # Doktor 1 (veya daha çok) karakteri yazmayı unutmuş. Yazılan kısa numara
    # elde, eksik karakterin pozisyonu belirsiz. Baştan `prefix` karakterin
    # kesinlikle baş olduğu biliniyorsa, eksik karakter(ler) `prefix`'ten
    # sonraki her boşluğa yerleştirilip tüm karakter seti denenir.
    @staticmethod
    def _norm_yazilan(yazilan: str) -> str:
        return "".join(c.upper() for c in (yazilan or "") if c.isalnum())

    def _eksik_gaps(self, yazilan_len: int, prefix: int):
        """Eksik karakterin girebileceği boşluk (gap) indeksleri.
        gap=p → yazılan dizide p indeksinden ÖNCE ekle (p=len → sona ekle)."""
        p = max(0, min(prefix, yazilan_len))
        return list(range(p, yazilan_len + 1))

    def eksik_bilgi(self, yazilan: str, prefix: int, hedef_uzunluk: int):
        """(yazilan_uzunluk, eksik_sayi, gap_sayisi, toplam) döndürür."""
        s = self._norm_yazilan(yazilan)
        L = len(s)
        M = hedef_uzunluk - L
        if M <= 0:
            return L, M, 0, 0
        from math import comb
        G = len(self._eksik_gaps(L, prefix))
        toplam = comb(G + M - 1, M) * (len(self.karakter_seti) ** M)
        return L, M, G, toplam

    @staticmethod
    def _yerlestir(s: str, gaps, chars):
        """gaps indekslerine chars karakterlerini yerleştir (sağdan sola)."""
        lst = list(s)
        for g, ch in sorted(zip(gaps, chars), key=lambda x: -x[0]):
            lst.insert(g, ch)
        return "".join(lst)

    def eksik_kombinasyonlar(self, yazilan: str, prefix: int, hedef_uzunluk: int):
        """Eksik karakter senaryosu için tüm adayları üretir (generator).

        Örn. yazilan='2OX5GH', prefix=3, hedef=7 →
             2OX?5GH → 2OX5?GH → 2OX5G?H → 2OX5GH?  (her ? için tüm set)
        """
        s = self._norm_yazilan(yazilan)
        L = len(s)
        M = hedef_uzunluk - L
        if M <= 0:
            return
        gaps = self._eksik_gaps(L, prefix)
        cs = self.karakter_seti
        for gap_combo in itertools.combinations_with_replacement(gaps, M):
            for chars in itertools.product(cs, repeat=M):
                yield self._yerlestir(s, gap_combo, chars)

    # ── Otomatik mod (DERECE-öncelikli karışma denemesi) ──────────────
    # Kullanıcı numarayı kesin gibi girer; sistem önce numarayı olduğu gibi
    # dener, sonra karışma ÇİFTLERİNİ rank sırasına göre (önce en sık) tek tek,
    # ardından ikili değiştirerek dener. `sabit_prefix` (varsayılan 3) kadar
    # ilk karakter DEĞİŞMEZ — yalnız son haneler (kalan 4) varyasyona girer.
    def _pos_alternatifleri(self, s: str, sabit_prefix: int):
        """Uygun (sabit_prefix sonrası) pozisyonlar için (pos, partner, rank)
        listesi — rank artan sırada."""
        alt = []
        for i in range(len(s)):
            if i < sabit_prefix:
                continue
            for partner, rank in self.tablo.alternatifler_sirali(s[i]):
                alt.append((i, partner, rank))
        alt.sort(key=lambda t: t[2])
        return alt

    def otomatik_bilgi(self, numara: str, sabit_prefix: int = 3,
                       max_degisim: int = 2):
        """(uzunluk, toplam_deneme) döndürür."""
        s = self._norm_yazilan(numara)
        n = len(s)
        if n == 0:
            return 0, 0
        tekli = self._pos_alternatifleri(s, sabit_prefix)
        toplam = 1 + len(tekli)              # orijinal + tekli değişimler
        if max_degisim >= 2:
            from collections import Counter
            pos_say = Counter(i for (i, _p, _r) in tekli)
            tum_cift = len(tekli) * (len(tekli) - 1) // 2
            ayni_poz = sum(c * (c - 1) // 2 for c in pos_say.values())
            toplam += (tum_cift - ayni_poz)  # farklı pozisyonlu ikili değişimler
        return n, toplam

    def otomatik_kombinasyonlar(self, numara: str, sabit_prefix: int = 3,
                                max_degisim: int = 2, kap: int = 4000):
        """Derece-öncelikli üreteç: orijinal → tekli değişimler (çift rank'ine
        göre) → ikili değişimler (rank toplamına göre). İlk `sabit_prefix`
        karakter sabit; yalnız sonrası varyasyona girer."""
        s = self._norm_yazilan(numara)
        n = len(s)
        if n == 0:
            return
        gorulen = set()

        def _ver(x):
            if x in gorulen:
                return None
            gorulen.add(x)
            return x

        # Mesafe 0 — orijinal
        x = _ver(s)
        if x is not None:
            yield x

        tekli = self._pos_alternatifleri(s, sabit_prefix)  # rank artan

        # Mesafe 1 — tekli değişimler (rank sırası)
        if max_degisim >= 1:
            for (i, partner, _r) in tekli:
                lst = list(s)
                lst[i] = partner
                x = _ver("".join(lst))
                if x is not None:
                    yield x
                    if len(gorulen) >= kap:
                        return

        # Mesafe 2 — ikili değişimler (farklı pozisyon, rank toplamına göre)
        if max_degisim >= 2:
            ikili = []
            for a in range(len(tekli)):
                i1, p1, r1 = tekli[a]
                for b in range(a + 1, len(tekli)):
                    i2, p2, r2 = tekli[b]
                    if i1 == i2:
                        continue
                    ikili.append((r1 + r2, i1, p1, i2, p2))
            ikili.sort(key=lambda t: t[0])
            for (_rs, i1, p1, i2, p2) in ikili:
                lst = list(s)
                lst[i1] = p1
                lst[i2] = p2
                x = _ver("".join(lst))
                if x is not None:
                    yield x
                    if len(gorulen) >= kap:
                        return

    def ozet_satirlari(self, pozisyonlar):
        """Her aktif pozisyon için ('P1', 'KESİN', ['2']) benzeri özet."""
        ks = self.karakter_seti
        satirlar = []
        i = 0
        for p in pozisyonlar:
            if not p.aktif:
                continue
            i += 1
            durum, adaylar = p.durum_ozeti(ks, self.tablo)
            satirlar.append((f"P{i}", durum, adaylar))
        return satirlar


# ── Basit özdenetim ────────────────────────────────────────────────────────
if __name__ == "__main__":
    motor = CozucuMotor()

    # Kullanıcı örneği: 20MI15S — P4 benzet="I", P6/P7 elle
    poz = [
        Pozisyon(kesin="2"),
        Pozisyon(kesin="0"),
        Pozisyon(kesin="M"),
        Pozisyon(benzet="I"),        # I → I,1,L,T,J...
        Pozisyon(kesin="1"),
        Pozisyon(olasi="5"),
        Pozisyon(olasi="S,5"),
    ]
    print("Toplam kombinasyon:", motor.toplam_kombinasyon(poz))
    print("Özet:")
    for ad, durum, adaylar in motor.ozet_satirlari(poz):
        print(f"  {ad}: {durum} -> {adaylar}")
    print("İlk 12 deneme:")
    for i, k in enumerate(motor.kombinasyonlar(poz)):
        print("  ", k)
        if i >= 11:
            break

    # Karma: benzet + elle birlikte (union)
    print("\nKarma P: kesin boş, olasi='X', benzet='O'")
    pk = Pozisyon(olasi="X", benzet="O")
    print("  adaylar:", pk.adaylar(motor.karakter_seti, motor.tablo))

    # Tamamen boş pozisyon -> tüm set
    poz2 = [Pozisyon(kesin="A"), Pozisyon(), Pozisyon(kesin="B")]
    print("\nBoş pozisyonlu toplam:", motor.toplam_kombinasyon(poz2), "(A?B)")
