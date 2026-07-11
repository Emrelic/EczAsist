# -*- coding: utf-8 -*-
"""
T.C. Kimlik Numarası — doğrulama, kontrol hanesi hesaplama ve
eksik (gizli) haneleri tamamlama.

🔑 KRİTİK GERÇEK: 11 haneli TC'nin son 2 hanesi (10. ve 11.) rastgele DEĞİL,
ilk 9 haneden matematiksel olarak HESAPLANIR. Dolayısıyla ilk 9 hane belliyse
son 2 hane için "deneme" yapmaya gerek yoktur — tek bir geçerli TC vardır.

Resmî (NVİ doğrulamasıyla uyuşan) algoritma:
  d1..d9 : ilk 9 hane (d1 ≠ 0)
  d10 = ((d1+d3+d5+d7+d9) * 7  -  (d2+d4+d6+d8)) mod 10
  d11 = (d1+d2+...+d10) mod 10

Not: İnternette yaygın dolaşan "ilk 9'u topla / 2'ye böl" veya "tek×1, çift×3"
biçimleri YANLIŞTIR; yukarıdaki formül doğrudur (örn. 10000000146 geçerli:
d10=4, d11=6 verir).

Gizli hane senaryosu: '452683307XX' → ilk 9 = 452683307 → d10=4, d11=2 →
tek geçerli TC = 45268330742. Bir iç hane de belirsizse (örn. '4526833_742'),
tüm olası dolgular denenip yalnız GEÇERLİ olanlar aday olarak döner.
"""

import itertools

# TC girişinde joker (bilinmeyen) kabul edilen karakterler
_JOKERLER = set("Xx_?*.-")


def kontrol_hane_10(ilk9) -> int:
    """İlk 9 haneden 10. haneyi hesapla. ilk9: 9 int'lik dizi."""
    tek = ilk9[0] + ilk9[2] + ilk9[4] + ilk9[6] + ilk9[8]   # 1,3,5,7,9
    cift = ilk9[1] + ilk9[3] + ilk9[5] + ilk9[7]            # 2,4,6,8
    return ((tek * 7) - cift) % 10


def kontrol_hane_11(ilk10) -> int:
    """İlk 10 haneden 11. haneyi hesapla. ilk10: 10 int'lik dizi."""
    return sum(ilk10) % 10


def tc_gecerli_mi(tc: str) -> bool:
    """11 haneli, ilk hanesi 0 olmayan ve kontrol haneleri tutan TC mi?"""
    if not tc or len(tc) != 11 or not tc.isdigit():
        return False
    d = [int(c) for c in tc]
    if d[0] == 0:
        return False
    if kontrol_hane_10(d[:9]) != d[9]:
        return False
    if kontrol_hane_11(d[:10]) != d[10]:
        return False
    return True


def tc_tamamla(ilk9: str) -> str:
    """9 haneli başlangıçtan tam 11 haneli geçerli TC üretir (tek sonuç).
    Geçersiz giriş → None."""
    ilk9 = (ilk9 or "").strip()
    if len(ilk9) != 9 or not ilk9.isdigit() or ilk9[0] == "0":
        return None
    d = [int(c) for c in ilk9]
    d10 = kontrol_hane_10(d)
    d11 = kontrol_hane_11(d + [d10])
    return ilk9 + str(d10) + str(d11)


def _desen_coz(giris: str):
    """Kullanıcı girdisini 11 slotluk desene çevirir (int veya None=joker).

    Kabul edilen biçimler:
      - 11 karakter: rakam veya joker (X/x/_/?/*/-/.), örn. '452683307XX'
      - 9 rakam: son 2 hane joker sayılır → '452683307' == '452683307??'
      - 10 rakam: son 1 hane joker
    Dönüş: 11 elemanlı liste [int|None] veya geçersizse None.
    """
    if not giris:
        return None
    s = "".join(giris.split())  # boşlukları at
    # Sadece rakamsa ve 9/10 uzunluksa → sona joker ekle
    if s.isdigit():
        if len(s) == 9:
            s = s + "??"
        elif len(s) == 10:
            s = s + "?"
        elif len(s) != 11:
            return None
    if len(s) != 11:
        return None
    slots = []
    for ch in s:
        if ch.isdigit():
            slots.append(int(ch))
        elif ch in _JOKERLER:
            slots.append(None)
        else:
            return None
    return slots


def tc_adaylari(giris: str, max_aday: int = 5000):
    """Desendeki jokerleri doldurup GEÇERLİ tüm TC adaylarını döndürür.

    Son 2 hane (kontrol haneleri) her zaman hesaplanır; joker olan ilk-9
    haneleri 0-9 arası denenir ve yalnız geçerli kombinasyonlar döner.

    Örn. '452683307XX' → ['45268330742']  (tek aday)
         '4526833_7XX' → ilk-9'daki tek joker için ≤10 geçerli aday
    Geçersiz giriş → [].
    """
    slots = _desen_coz(giris)
    if slots is None:
        return []
    serbest9 = [i for i in range(9) if slots[i] is None]  # ilk-9'daki jokerler
    sabit10 = slots[9]    # 10. hane sabit mi?
    sabit11 = slots[10]   # 11. hane sabit mi?
    adaylar = []
    for kombo in itertools.product(range(10), repeat=len(serbest9)):
        d = [slots[i] for i in range(9)]
        for idx, val in zip(serbest9, kombo):
            d[idx] = val
        if d[0] == 0:
            continue
        d10 = kontrol_hane_10(d)
        if sabit10 is not None and sabit10 != d10:
            continue
        d11 = kontrol_hane_11(d + [d10])
        if sabit11 is not None and sabit11 != d11:
            continue
        adaylar.append("".join(str(x) for x in d) + str(d10) + str(d11))
        if len(adaylar) >= max_aday:
            break
    return adaylar


def hasta_ara(isim: str, limit: int = 10):
    """Botanik EOS `Musteri` tablosunda isme göre hasta arar (🔒 SADECE SELECT).

    Girilen isimdeki her kelime (≥2 harf) AdSoyadi içinde AND'lenir → sıra
    fark etmeksizin eşleşir. **Sıralama: eczaneye en çok gelen (en çok reçetesi
    olan) hastalar önce** (ReceteAna adedine göre azalan). Dönüş: list[dict]
    {'tc','ad','adet'} (yalnız 11 haneli geçerli TC'liler). DB yoksa/hata → [].
    """
    isim = (isim or "").strip()
    kelimeler = [k for k in isim.split() if len(k) >= 2]
    if not kelimeler:
        return []
    try:
        from botanik_db import get_botanik_db
        db = get_botanik_db()
    except Exception:
        return []
    try:
        lim = max(1, min(50, int(limit)))
    except Exception:
        lim = 10
    kosul = " AND ".join(["m.MusteriAdiSoyadi LIKE ?"] * len(kelimeler))
    sql = (
        f"SELECT TOP {lim} m.MusteriTCKN AS tc, m.MusteriAdiSoyadi AS ad, "
        f"       COUNT(ra.RxId) AS adet "
        f"FROM Musteri m "
        f"LEFT JOIN ReceteAna ra ON ra.RxMusteriId = m.MusteriId AND ra.RxSilme = 0 "
        f"WHERE {kosul} AND m.MusteriTCKN IS NOT NULL "
        f"GROUP BY m.MusteriTCKN, m.MusteriAdiSoyadi "
        f"ORDER BY COUNT(ra.RxId) DESC, m.MusteriAdiSoyadi"
    )
    params = tuple(f"%{k}%" for k in kelimeler)
    try:
        rows = db.sorgu_calistir(sql, params)
    except Exception:
        return []
    sonuc = []
    for r in rows or []:
        tc = str(r.get("tc") or "").strip()
        ad = str(r.get("ad") or "").strip()
        if len(tc) == 11 and tc.isdigit():
            try:
                adet = int(r.get("adet") or 0)
            except Exception:
                adet = 0
            sonuc.append({"tc": tc, "ad": ad, "adet": adet})
    return sonuc


def durum_ozeti(giris: str):
    """UI için: (durum_metni, aday_sayisi, ilk_aday). Girişi yorumlar."""
    s = "".join((giris or "").split())
    if not s:
        return "boş", 0, None
    adaylar = tc_adaylari(s)
    n = len(adaylar)
    if n == 0:
        # Tam 11 rakam ama geçersizse ayrı mesaj
        if s.isdigit() and len(s) == 11:
            return "geçersiz TC (kontrol haneleri tutmuyor)", 0, None
        return "geçersiz / tamamlanamıyor", 0, None
    if n == 1:
        if s.isdigit() and len(s) == 11 and s == adaylar[0]:
            return "geçerli TC", 1, adaylar[0]
        return f"tamamlandı → {adaylar[0]}", 1, adaylar[0]
    return f"{n} olası TC (denenecek)", n, adaylar[0]


if __name__ == "__main__":
    # Doğrulama: bilinen geçerli test numarası
    print("10000000146 geçerli mi:", tc_gecerli_mi("10000000146"))  # True bekleniyor
    print("Örnek tamamla 452683307 →", tc_tamamla("452683307"))
    print("Desen '452683307XX' adayları:", tc_adaylari("452683307XX"))
    print("9 hane '452683307' adayları:", tc_adaylari("452683307"))
    print("İç joker '4526833_7XX' aday sayısı:", len(tc_adaylari("4526833?7XX")))
    print("Durum özeti '452683307XX':", durum_ozeti("452683307XX"))
    print("Geçersiz '12345678901' geçerli mi:", tc_gecerli_mi("12345678901"))
