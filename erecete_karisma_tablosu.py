# -*- coding: utf-8 -*-
"""
E-Reçete Çözücü — Karakter Karışma Tablosu

Doktorların okunmaz el yazısında birbirine benzeyen / karıştırılan
karakterleri tutar. Her "klik" (clique) satırı, o gruptaki karakterlerin
birbiriyle karışabileceğini ifade eder.

Kullanım:
    tablo = KarismaTablosu()
    tablo.genislet("O")   -> ['O', 'Q', '0', 'D', 'C', 'A']  (sıra korunur)
    tablo.setler_ekle("ABC")
    tablo.kaydet()

Veri, yerel JSON dosyasında saklanır ve ayar penceresinden düzenlenebilir.
Uygulamadaki tek meşru okuma/yazma noktası budur (Botanik EOS ile ilgisi
yoktur — tamamen yerel bir yapılandırma dosyasıdır).
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_DIZIN = os.path.dirname(os.path.abspath(__file__))
KARISMA_JSON = os.path.join(_DIZIN, "erecete_karisma_tablosu.json")

# Geçerli e-reçete karakter seti (büyük harf + rakam).
# Bir pozisyon "tamamen bilinmiyor" ise bu setin tamamı sırayla denenir.
VARSAYILAN_KARAKTER_SETI = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ── Varsayılan karışma setleri ────────────────────────────────────────────
# Kullanıcının verdiği setler + literatür (NIH PMC3541865 el-yazısı ilaç
# karışıklıkları, Unicode confusables) eklemeleri. Her string bir klik'tir:
# içindeki karakterlerin hepsi birbiriyle karışabilir kabul edilir.
# Küçük harfler büyük harfe normalize edilir (Medula e-reçete no büyük harf).
VARSAYILAN_SETLER = [
    # ── Kullanıcının verdiği setler ──
    "QO0DC",     # Q O 0 D C — yuvarlak gövdeliler
    "8B",        # 8 B
    "1ILl",      # 1 I L (küçük l)
    "Z2",        # Z 2
    "5S9",       # 5 S 9
    "G96",       # G 9 6
    "1TIl",      # 1 T I (küçük l)
    "IJL",       # I J L
    "VU",        # V U
    "WMNVYU",    # W M N V Y U
    "G69",       # G 6 9
    "A4",        # A 4
    "XKRB",      # X K R B
    "QPq",       # Q P (küçük q)
    "FEB",       # F E B
    "3EZ",       # 3 E Z
    "7YZ21",     # 7 Y Z 2 1
    "PR",        # P R
    # ── Literatür / araştırma eklemeleri ──
    "O0",        # O 0  (en sık — Unicode homoglyph)
    "1l",        # 1 l  (en sık — el/bir)
    "S58",       # S 5 8 (NIH: S/5, S/8, 5/8)
    "53",        # 5 3   (NIH)
    "T7",        # T 7   (NIH)
    "TI",        # T I   (NIH — yatay çizgi/serif)
    "Z7",        # Z 7   (NIH)
    "17",        # 1 7   (NIH — yüksek riskli)
    "EF",        # E F   (NIH)
    "GQ",        # G Q   (küçük g/q el yazısı)
    "CE",        # C E   (küçük c/e el yazısı)
    "LB",        # L B   (kursif l/b)
    "AO",        # A O   (kursif a/o)
    "G6",        # G 6
    "DO",        # D O
    "D0",        # D 0
]


def _norm(ch: str) -> str:
    """Tek karakteri normalize et: büyük harf. (TR İ/I sorununu önlemek için
    ASCII upper; e-reçete karakterleri zaten ASCII.)"""
    if not ch:
        return ""
    c = ch.strip()
    if not c:
        return ""
    # Türkçe küçük 'i' → 'I', 'ı' → 'I' vb. yerine ASCII davranışı yeterli;
    # e-reçete karakter seti ASCII olduğundan basit upper güvenli.
    return c[0].upper()


def parse_karakterler(metin: str):
    """Kullanıcının olası-karakterler girdisini ayrıştırır.

    Virgül, boşluk, noktalı virgül, tire veya bitişik — hepsi aynı şekilde
    değerlendirilir. Her anlamlı karakter tek tek alınır, büyük harfe
    çevrilir, sırası korunarak tekilleştirilir.

        "O,Q,0,D"  -> ['O','Q','0','D']
        "QO0D"     -> ['Q','O','0','D']
        "Q D O 0"  -> ['Q','D','O','0']
    """
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
    """Karışma setlerini yükler, genişletme yapar, düzenler ve kaydeder."""

    def __init__(self, dosya: str = KARISMA_JSON):
        self.dosya = dosya
        self.setler = []           # list[str]  (her biri bir klik)
        self.karakter_seti = VARSAYILAN_KARAKTER_SETI
        self.yukle()

    # ── Yükleme / kaydetme ────────────────────────────────────────────
    def yukle(self):
        """JSON'dan yükle; yoksa varsayılanları kullan (ve dosyayı oluştur)."""
        if os.path.exists(self.dosya):
            try:
                with open(self.dosya, "r", encoding="utf-8") as f:
                    veri = json.load(f)
                self.setler = [str(s) for s in veri.get("setler", [])]
                self.karakter_seti = str(
                    veri.get("karakter_seti", VARSAYILAN_KARAKTER_SETI)
                )
                if not self.setler:
                    self.setler = list(VARSAYILAN_SETLER)
                self._indeks_kur()
                return
            except Exception as e:
                logger.warning(f"Karışma tablosu okunamadı, varsayılan: {e}")
        # Dosya yok / bozuk → varsayılan
        self.setler = list(VARSAYILAN_SETLER)
        self.karakter_seti = VARSAYILAN_KARAKTER_SETI
        self._indeks_kur()
        try:
            self.kaydet()
        except Exception:
            pass

    def kaydet(self):
        """Setleri JSON'a yaz."""
        veri = {
            "setler": self.setler,
            "karakter_seti": self.karakter_seti,
        }
        with open(self.dosya, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        self._indeks_kur()
        logger.info(f"Karışma tablosu kaydedildi ({len(self.setler)} set)")

    # ── İndeks (karakter -> komşular) ─────────────────────────────────
    def _indeks_kur(self):
        """Her karakter için, aynı klikte bulunduğu tüm karakterleri topla.
        Sıra korunur (ilk görülme sırasına göre)."""
        self._komsu = {}   # char -> list[char]
        for s in self.setler:
            uyeler = []
            for ch in s:
                u = _norm(ch)
                if u and u not in uyeler:
                    uyeler.append(u)
            for u in uyeler:
                lst = self._komsu.setdefault(u, [])
                for v in uyeler:
                    if v not in lst:
                        lst.append(v)

    # ── Genişletme ────────────────────────────────────────────────────
    def genislet(self, karakter: str, kendini_dahil_et: bool = True):
        """Bir karakterin karışabileceği tüm karakterleri döndürür.

        Örn. genislet("7") -> ['7','Y','Z','2','1','T'] (setlere göre).
        Geçerli karakter setiyle sınırlanır. Sıra: önce kendisi, sonra
        klik'lerdeki görülme sırası.
        """
        u = _norm(karakter)
        if not u:
            return []
        komsu = self._komsu.get(u, [])
        sonuc = []
        if kendini_dahil_et and u in self.karakter_seti:
            sonuc.append(u)
        for v in komsu:
            if v != u and v in self.karakter_seti and v not in sonuc:
                sonuc.append(v)
        # Kendisi setler dışıysa yine de dahil et (kullanıcı özel giriş)
        if kendini_dahil_et and u not in sonuc:
            sonuc.insert(0, u)
        return sonuc

    def genislet_metin(self, metin: str):
        """Bir metindeki HER karakteri genişletip birleştirir (tekil, sıralı).
        Kullanıcı olası kutusuna 'benzetilen' karakter(ler) yazıp genişletme
        istediğinde kullanılır. Örn. '7' -> ['7','Y','Z','2','1','T']."""
        cikti = []
        for ch in parse_karakterler(metin):
            for v in self.genislet(ch):
                if v not in cikti:
                    cikti.append(v)
        return cikti

    # ── Düzenleme (ayar penceresi) ────────────────────────────────────
    def set_ekle(self, metin: str):
        """Yeni bir karışma seti ekle (en az 2 farklı karakter)."""
        uyeler = parse_karakterler(metin)
        if len(uyeler) < 2:
            raise ValueError("Bir karışma seti en az 2 farklı karakter içermeli.")
        yeni = "".join(uyeler)
        if yeni not in self.setler:
            self.setler.append(yeni)
        self._indeks_kur()
        return yeni

    def set_sil(self, indeks: int):
        if 0 <= indeks < len(self.setler):
            self.setler.pop(indeks)
            self._indeks_kur()

    def set_guncelle(self, indeks: int, metin: str):
        uyeler = parse_karakterler(metin)
        if len(uyeler) < 2:
            raise ValueError("Bir karışma seti en az 2 farklı karakter içermeli.")
        if 0 <= indeks < len(self.setler):
            self.setler[indeks] = "".join(uyeler)
            self._indeks_kur()

    def varsayilana_don(self):
        self.setler = list(VARSAYILAN_SETLER)
        self.karakter_seti = VARSAYILAN_KARAKTER_SETI
        self._indeks_kur()


# Kolay kullanım için tekil örnek (lazy)
_ORNEK = None


def get_tablo() -> "KarismaTablosu":
    global _ORNEK
    if _ORNEK is None:
        _ORNEK = KarismaTablosu()
    return _ORNEK


if __name__ == "__main__":
    t = KarismaTablosu()
    print("Set sayısı:", len(t.setler))
    for ornek in ["O", "7", "5", "1", "G", "B", "S", "Z"]:
        print(f"  {ornek} -> {t.genislet(ornek)}")
