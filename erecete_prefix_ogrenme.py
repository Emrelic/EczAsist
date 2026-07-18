# -*- coding: utf-8 -*-
"""
E-Reçete / Takip numarası PREFIX ÖĞRENME

Aynı dönemde (o günlerde) verilen e-reçete numaraları ortak bir prefix'le
başlar (örn. '2OX…'), takip numaraları farklı bir prefix'le (örn. '59C…') —
çünkü ardışık üretilen numaralardır. Sistem bir reçeteyi e-reçete VEYA takip
numarasından bulduğunda, o numaranın **ilk 2 karakterini** ve türünü öğrenir.
Sonraki numara girildiğinde ilk 2 karaktere bakıp türü DOĞRUDAN belirler ve
önce onu dener (iki alanı da denemeye gerek kalmaz).

Kalıcılık: yerel JSON (`erecete_prefix_ogrenme.json`) — Botanik EOS değil.
Sınıflandırmada en güncel (tarih) ve en çok görülen (sayac) prefix öncelikli.
"""

import json
import os

try:
    from datetime import date
except Exception:
    date = None

_DIZIN = os.path.dirname(os.path.abspath(__file__))
OGRENME_JSON = os.path.join(_DIZIN, "erecete_prefix_ogrenme.json")

PREFIX_UZUNLUK = 3


def _bugun():
    try:
        return date.today().isoformat()
    except Exception:
        return ""


def _prefix(numara, n=PREFIX_UZUNLUK):
    s = "".join(c for c in (numara or "") if c.isalnum()).upper()
    return s[:n]


def _heuristik(numara):
    """Öğrenilmemişse: harf içeriyorsa e-reçete, tümü rakamsa takip."""
    s = "".join(c for c in (numara or "") if c.isalnum())
    if not s:
        return "erecete"
    return "takip" if s.isdigit() else "erecete"


def _norm(s):
    return "".join(c for c in (s or "") if c.isalnum()).upper()


def prefix_eslesme_skoru(numara, prefix):
    """Girilen `numara` ile bir `prefix` ne kadar örtüşüyor? (0 = uyuşmaz)

    - numara prefix ile TAM başlıyorsa → skor = len(prefix)  (prefix yazılmış bitmiş)
    - prefix numara ile başlıyorsa (kullanıcı hâlâ yazıyor) → skor = len(numara)
    - hiçbiri değilse → 0  (ilk karakterlerden itibaren çelişki var)

    Örn: numara='2P4X', prefix='2P4' → 3 · numara='2', prefix='2P4' → 1 ·
         numara='59X', prefix='2P4' → 0
    """
    s = _norm(numara)
    p = _norm(prefix)
    if not s or not p:
        return 0
    if s.startswith(p):
        return len(p)
    if p.startswith(s):
        return len(s)
    return 0


def medula_tip_belirle(numara, erecete_prefixler, takip_prefixler):
    """Medula E-Reçete Sorgu ekranındaki prefix tablosuna göre türü belirle.

    O tarihte/dönemde üretilen e-reçete numaraları (ör. 2P4, 2P3, 2P2) ve takip
    numaraları (ör. 59Y, 59X, 59W) farklı başlangıçlarla gelir. Girilen numaranın
    başı hangi listedeki bir prefix'le örtüşüyorsa tür odur. En uzun örtüşme
    kazanır; iki listede de eşit güçte örtüşme olursa (çelişki) belirsiz döner.

    Dönüş: (tip, eslesen_prefix, skor)
       tip ∈ {'erecete','takip',None}   None → tabloda net eşleşme yok/çelişki
    """
    def _en_iyi(prefixler):
        en_skor, en_p = 0, None
        for p in (prefixler or []):
            sk = prefix_eslesme_skoru(numara, p)
            if sk > en_skor:
                en_skor, en_p = sk, _norm(p)
        return en_skor, en_p

    ser, per = _en_iyi(erecete_prefixler)
    stk, ptk = _en_iyi(takip_prefixler)
    if ser == 0 and stk == 0:
        return None, None, 0          # tablo yok / hiçbirine uymuyor
    if ser > stk:
        return "erecete", per, ser
    if stk > ser:
        return "takip", ptk, stk
    return None, None, ser            # eşit skor, ikisine de uyuyor → çelişki


class PrefixOgrenme:
    def __init__(self, dosya: str = OGRENME_JSON):
        self.dosya = dosya
        self.kayitlar = []   # list[{prefix, tip, tarih, sayac}]
        self.yukle()

    def yukle(self):
        if os.path.exists(self.dosya):
            try:
                with open(self.dosya, "r", encoding="utf-8") as f:
                    self.kayitlar = json.load(f).get("kayitlar", [])
                return
            except Exception:
                pass
        self.kayitlar = []

    def kaydet(self):
        try:
            with open(self.dosya, "w", encoding="utf-8") as f:
                json.dump({"kayitlar": self.kayitlar}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass

    def ogren(self, tip: str, numara: str):
        """Başarılı sorgudan sonra prefix+tür öğren."""
        if tip not in ("erecete", "takip"):
            return
        p = _prefix(numara)
        if len(p) < PREFIX_UZUNLUK:
            return
        for k in self.kayitlar:
            if k.get("prefix") == p and k.get("tip") == tip:
                k["sayac"] = int(k.get("sayac", 0)) + 1
                k["tarih"] = _bugun()
                self.kaydet()
                return
        self.kayitlar.append(
            {"prefix": p, "tip": tip, "tarih": _bugun(), "sayac": 1})
        if len(self.kayitlar) > 200:
            self.kayitlar.sort(
                key=lambda k: (k.get("tarih", ""), int(k.get("sayac", 0))),
                reverse=True)
            self.kayitlar = self.kayitlar[:200]
        self.kaydet()

    def _eslesenler(self, numara):
        """Girilen numaranın prefix'iyle eşleşen kayıtlar. Önce tam 3 karakter,
        sonra 2, sonra 1 karakter (dönem değişiminde 3. karakter değişir ama
        ilk 2 sabit kalır) — güncel+sık önce sıralı."""
        recs = []
        for uzun in (3, 2, 1):
            p = _prefix(numara, uzun)
            if len(p) < uzun:
                continue
            recs = [k for k in self.kayitlar
                    if str(k.get("prefix", ""))[:uzun] == p]
            if recs:
                break
        recs.sort(key=lambda k: (k.get("tarih", ""), int(k.get("sayac", 0))),
                  reverse=True)
        return recs

    def tip_belirle(self, numara):
        """(tip, ogrenildi_mi) döndürür. Prefix biliniyorsa güvenle (True)
        o tür; değilse heuristikle (False)."""
        recs = self._eslesenler(numara)
        if recs:
            return recs[0].get("tip"), True
        return _heuristik(numara), False

    def eslesen_prefix(self, numara):
        """UI için: öğrenilmiş eşleşen prefix (str) veya None."""
        recs = self._eslesenler(numara)
        return recs[0].get("prefix") if recs else None

    def guncel_prefix(self, tip):
        """Bir tür için bilinen EN GÜNCEL 3-karakter prefix (auto-fill için)
        veya None."""
        recs = [k for k in self.kayitlar if k.get("tip") == tip]
        if not recs:
            return None
        recs.sort(key=lambda k: (k.get("tarih", ""), int(k.get("sayac", 0))),
                  reverse=True)
        return recs[0].get("prefix")

    def meduladan_kaydet(self, erecete_list, takip_list):
        """Medula prefix tablosundan okunan TÜM prefix'leri (o dönem/tarih
        aralığındaki e-reçete + takip başlangıçları) öğren. Liste en güncel
        önce sıralı gelir; hepsi kaydedilir ki eski (birkaç gün önceki) bir
        numara girildiğinde de doğru tür bulunabilsin."""
        for p in (erecete_list or []):
            self.ogren("erecete", p)
        for p in (takip_list or []):
            self.ogren("takip", p)


_ORNEK = None


def get_ogrenme() -> "PrefixOgrenme":
    global _ORNEK
    if _ORNEK is None:
        _ORNEK = PrefixOgrenme()
    return _ORNEK


if __name__ == "__main__":
    o = PrefixOgrenme(dosya=os.path.join(_DIZIN, "_test_prefix.json"))
    o.kayitlar = []
    o.ogren("erecete", "2OMRI1J")
    o.ogren("takip", "59C1234")
    print("2OX... →", o.tip_belirle("2OX5HJY"))   # erecete, True
    print("59C... →", o.tip_belirle("59C0000"))   # takip, True
    print("bilinmeyen 7X →", o.tip_belirle("7XABCDE"))  # heuristik, False
    print("rakam →", o.tip_belirle("1234567"))    # takip (heuristik), False
    try:
        os.remove(os.path.join(_DIZIN, "_test_prefix.json"))
    except Exception:
        pass
