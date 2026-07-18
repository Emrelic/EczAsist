"""
SGK Barem / İskonto Etki Hesaplayıcı — hesap motoru.

Eczanenin ciro yapısına göre SGK iskonto baremini, tek bir (pahalı) reçetenin
kârını ve o reçetenin hasılatı şişirmesi yüzünden GELECEK YIL SGK'ya yapılacak
ekstra iskonto/hizmet bedeli kaybını hesaplar.

Mevzuat temeli:
- 2026/1 Ek Protokol (SGK-TEB, 12.03.2026) Madde 2: iskonto baremleri (6 dilim)
  ve reçete başı hizmet bedelleri (7 dilim), 01.10.2025'ten geçerli.
- Barem, bir önceki yıl TOPLAM satış hasılatına (KDV hariç, nakit dahil) göre
  belirlenir; iskonto yalnız SGK reçetelerine uygulanır (SUT 4.4.1/12).
- Depocu fiyatlı ilaçlar (kan ürünü, enzim, bazı mama/radyofarmasötik):
  eczacı indirimi UYGULANMAZ (SUT 4.4.1/11) ama tutarları hasılata girer.
- Kademeli kâr: Karar 11031 dilimleri (gelir vergisi gibi kümülatif).

Kurallar barem_kurallari.json'dan okunur (yıl bazlı, elle güncellenebilir).
"""

import json
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_VARSAYILAN_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "barem_kurallari.json")


def kurallari_yukle(json_yolu: Optional[str] = None) -> Dict:
    """barem_kurallari.json'u oku ve döndür."""
    yol = json_yolu or _VARSAYILAN_JSON
    with open(yol, "r", encoding="utf-8") as f:
        return json.load(f)


def yil_konfig(kurallar: Dict, yil: Optional[str] = None) -> Dict:
    """İstenen (veya aktif) yılın barem konfigürasyonunu döndür."""
    yil = str(yil or kurallar.get("aktif_yil"))
    yillar = kurallar.get("yillar", {})
    if yil not in yillar:
        raise KeyError(f"barem_kurallari.json içinde '{yil}' yılı tanımlı değil")
    return yillar[yil]


def _dilim_bul(baremler: List[Dict], hasilat: float, esik_carpani: float = 1.0) -> int:
    """hasilat'ın düştüğü dilimin indeksini döndür (ust=None → sonsuz).

    esik_carpani: dilim eşiklerini ölçekler (gelecek dönem barem artış beklentisi —
    baremler her yıl protokol/enflasyonla artırılır, bu yılın hasılatı GELECEKTE
    ilan edilecek yüksek eşiklerle kıyaslanır).
    """
    for i, dilim in enumerate(baremler):
        ust = dilim.get("ust")
        if ust is None or hasilat <= ust * esik_carpani:
            return i
    return len(baremler) - 1


def barem_bilgi(hasilat: float, cfg: Dict, esik_carpani: float = 1.0) -> Dict:
    """Verilen yıllık hasılat için iskonto oranı + hizmet bedeli + dilim bilgisi.

    Returns:
        {
          'hasilat', 'iskonto_orani', 'iskonto_dilim' (0-bazlı),
          'hizmet_bedeli', 'hizmet_dilim',
          'iskonto_ust_esik' (bir üst iskonto dilimine geçilen eşik, None=son dilim),
          'iskonto_bareme_kalan' (eşiğe kalan TL, None=son dilim),
          'hizmet_ust_esik', 'hizmet_bareme_kalan'
        }
    """
    isk = cfg["iskonto_baremleri"]
    hb = cfg["hizmet_bedeli_baremleri"]
    i_idx = _dilim_bul(isk, hasilat, esik_carpani)
    h_idx = _dilim_bul(hb, hasilat, esik_carpani)

    i_ust = isk[i_idx].get("ust")
    i_ust = i_ust * esik_carpani if i_ust is not None else None
    h_ust = hb[h_idx].get("ust")
    h_ust = h_ust * esik_carpani if h_ust is not None else None
    return {
        "hasilat": hasilat,
        "esik_carpani": esik_carpani,
        "iskonto_orani": isk[i_idx]["oran"],
        "iskonto_dilim": i_idx,
        "hizmet_bedeli": hb[h_idx]["tutar"],
        "hizmet_dilim": h_idx,
        "iskonto_ust_esik": i_ust,
        "iskonto_bareme_kalan": (i_ust - hasilat) if i_ust is not None else None,
        "hizmet_ust_esik": h_ust,
        "hizmet_bareme_kalan": (h_ust - hasilat) if h_ust is not None else None,
    }


def kademeli_kar(dsf: float, dilimler: List[Dict], alan: str = "eczaci") -> float:
    """Depocu satış fiyatı (DSF) üzerinden kümülatif kademeli kâr tutarı.

    Gelir vergisi dilimleri gibi: ilk dilime o dilimin oranı, taşan kısma
    bir sonraki dilimin oranı uygulanır (Karar 11031 sistemi).
    """
    kar = 0.0
    onceki_ust = 0.0
    for dilim in dilimler:
        ust = dilim.get("ust")
        oran = dilim[alan]
        if ust is None or dsf <= ust:
            kar += (dsf - onceki_ust) * oran
            return kar
        kar += (ust - onceki_ust) * oran
        onceki_ust = ust
    return kar


def recete_kari(
    tutar: float,
    alis: Optional[float] = None,
    karlilik_orani: Optional[float] = None,
    iskontoya_tabi: bool = True,
    iskonto_orani: float = 0.0,
    hizmet_bedeli: float = 0.0,
    mobil_soguk: bool = False,
    hizmet_carpani: float = 1.5,
    oda_katki_orani: float = 0.0,
) -> Dict:
    """Tek reçetenin bu yılki net kârı.

    Brüt kâr: alis verilmişse (tutar - alis), yoksa tutar * karlilik_orani.
    İskonto: reçete iskontoya tabiyse tutar * iskonto_orani (kan ürünü/enzim
    gibi depocu fiyatlı reçetelerde 0).
    Hizmet bedeli: reçete başına sabit; mobil+soğuk zincirde çarpanlı.
    Oda katkı payı: sıralı dağıtım reçetelerinde oda onayında tutar üzerinden
    kesilen pay (odaya göre ~%0,3-0,5); sıralı dağıtım değilse 0 geçilir.
    """
    if alis is not None:
        brut = tutar - alis
    elif karlilik_orani is not None:
        brut = tutar * karlilik_orani
    else:
        raise ValueError("alis veya karlilik_orani girilmeli")

    iskonto = tutar * iskonto_orani if iskontoya_tabi else 0.0
    oda_katki = tutar * oda_katki_orani
    hb = hizmet_bedeli * (hizmet_carpani if mobil_soguk else 1.0)
    return {
        "brut_kar": brut,
        "iskonto_kesintisi": iskonto,
        "oda_katki_payi": oda_katki,
        "hizmet_bedeli": hb,
        "net_kar": brut - iskonto - oda_katki + hb,
    }


def fiyat_karlilik_tablosu(dsf_listesi: List[float], dilimler: List[Dict]) -> List[Dict]:
    """İlaç fiyatı (DSF) değiştikçe eczacı kârlılığının nasıl değiştiğini hesapla.

    Eczane alışı ≈ DSF (depodan), satışı (KDV hariç) = DSF + kademeli eczacı kârı.
    Kâr oranı kademeli sistem yüzünden fiyat arttıkça marjinal dilime yakınsar.

    Returns: [{dsf, kar, satis, kar_alis_orani, kar_satis_orani, marjinal_oran}, ...]
    """
    sonuc = []
    for dsf in dsf_listesi:
        kar = kademeli_kar(dsf, dilimler, "eczaci")
        satis = dsf + kar
        marjinal = dilimler[_dilim_bul(dilimler, dsf)]["eczaci"]
        sonuc.append({
            "dsf": dsf,
            "kar": kar,
            "satis": satis,
            "kar_alis_orani": kar / dsf if dsf > 0 else 0.0,
            "kar_satis_orani": kar / satis if satis > 0 else 0.0,
            "marjinal_oran": marjinal,
        })
    return sonuc


def personel_tam_maliyet(
    brut_ucret: float,
    parametreler: Dict,
    fazla_mesai: bool = True,
    yemek: bool = True,
) -> Dict:
    """Bir çalışanın aylık TAM işveren maliyeti.

    Bileşenler:
    - Brüt ücret + SGK işveren (%21,75) + işsizlik işveren (%2) − Hazine teşviki (2 puan)
    - Azami fazla mesai: İş K. m.41, 270 saat/yıl (aylık 22,5 saat), %50 zamlı,
      prime/vergiye tabi → aynı işveren çarpanıyla maliyete girer
    - Yemek bedeli: günlük tutar × gün sayısı (vergi istisnası sınırında, prim etkisi ihmal)
    """
    p = parametreler
    carpan = (1.0 + p["sgk_isveren_orani"] + p["issizlik_isveren_orani"]
              - p.get("hazine_tesvik_puan", 0.0))

    fm_brut = 0.0
    if fazla_mesai:
        aylik_fm_saat = p["fazla_mesai_yillik_azami_saat"] / 12.0
        saat_ucreti = brut_ucret / p["aylik_calisma_saati"]
        fm_brut = saat_ucreti * p["fazla_mesai_zam_carpani"] * aylik_fm_saat

    yemek_tutar = (p["yemek_gunluk"] * p["yemek_gun_sayisi"]) if yemek else 0.0

    ucret_maliyeti = brut_ucret * carpan
    fm_maliyeti = fm_brut * carpan
    toplam = ucret_maliyeti + fm_maliyeti + yemek_tutar
    return {
        "brut_ucret": brut_ucret,
        "isveren_carpani": carpan,
        "ucret_maliyeti": ucret_maliyeti,
        "fazla_mesai_brut": fm_brut,
        "fazla_mesai_maliyeti": fm_maliyeti,
        "yemek_tutari": yemek_tutar,
        "aylik_toplam": toplam,
        "yillik_toplam": toplam * 12.0,
    }


def istihdam_varsayilan_maliyetler(
    kurallar: Dict,
    fazla_mesai: bool = True,
    yemek: bool = True,
) -> Dict:
    """İkinci ve yardımcı eczacının aylık tam işveren maliyeti (yasal tabanlardan).

    Yönetmelik m.16/5: yardımcı ≥ 1,5x, ikinci ≥ 3x asgari ücret (BRÜT üzerinden).
    """
    p = kurallar["istihdam"]["maliyet_parametreleri"]
    ikinci_brut = p["asgari_ucret_brut"] * p["ikinci_eczaci_kat"]
    yardimci_brut = p["asgari_ucret_brut"] * p["yardimci_eczaci_kat"]
    return {
        "ikinci": personel_tam_maliyet(ikinci_brut, p, fazla_mesai, yemek),
        "yardimci": personel_tam_maliyet(yardimci_brut, p, fazla_mesai, yemek),
    }


def istihdam_konfig(kurallar: Dict, yil: Optional[str] = None) -> Dict:
    """İstihdam (ikinci/yardımcı eczacı) eşik konfigürasyonunu döndür."""
    ist = kurallar.get("istihdam", {})
    yil = str(yil or ist.get("aktif_yil"))
    yillar = ist.get("yillar", {})
    if yil not in yillar:
        raise KeyError(f"istihdam kriterleri için '{yil}' yılı tanımlı değil")
    return yillar[yil]


def _asilan_kat_sayisi(deger: float, esik: float) -> int:
    """Eşiğin AŞILAN tam kat sayısı (Yönetmelik m.16: 'aşılması halinde').

    Tam eşitlik 'aşılmış' sayılmaz: değer = 1x eşik → 0, değer = 1x eşik + 1 kuruş → 1.
    """
    if esik <= 0 or deger <= esik:
        return 0
    n = int(deger // esik)
    if deger == n * esik:  # tam katta: o kat henüz aşılmadı
        n -= 1
    return n


def istihdam_durumu(hasilat: float, yillik_recete: float, ist_cfg: Dict,
                    esik_carpani: float = 1.0) -> Dict:
    """Verilen hasılat + reçete sayısı için istihdam yükümlülüğü.

    Yönetmelik m.16: yıllık 80.000 reçete VEYA eşik tutarında cironun AŞILMASI
    halinde ikinci eczacı; eklenen her eşik katı için ilave (azami 3). İki veri
    de uygunsa daha fazla ikinci eczacı gerektiren esas alınır (max). Reçete
    sayısı Kurum (SGK) verisidir; ciro Kuruma bildirilen KDV hariç hasılattır.
    Yardımcı eczacı: hasılat eşiğinin aşılması halinde 1.
    """
    ikinci_h = ist_cfg["ikinci_eczaci_hasilat_esigi"] * esik_carpani
    ikinci_r = ist_cfg["ikinci_eczaci_recete_esigi"]  # reçete adedi eşiği sabit (80.000)
    yardimci_h = ist_cfg["yardimci_eczaci_hasilat_esigi"] * esik_carpani
    azami = ist_cfg.get("azami_ikinci_eczaci", 3)

    n_hasilat = _asilan_kat_sayisi(hasilat, ikinci_h)
    n_recete = _asilan_kat_sayisi(yillik_recete, ikinci_r)
    ikinci_sayisi = min(azami, max(n_hasilat, n_recete))

    yardimci_gerekli = hasilat > yardimci_h

    # Bir sonraki yükümlülük eşiğine (hasılat üzerinden) kalan mesafe
    sonraki_ikinci_esik = (ikinci_sayisi + 1) * ikinci_h if ikinci_sayisi < azami else None
    return {
        "ikinci_sayisi": ikinci_sayisi,
        "yardimci_gerekli": yardimci_gerekli,
        "ikinci_esik": ikinci_h,
        "recete_esigi": ikinci_r,
        "yardimci_esik": yardimci_h,
        "ikinci_esige_kalan": (sonraki_ikinci_esik - hasilat)
        if sonraki_ikinci_esik is not None else None,
        "yardimci_esige_kalan": (yardimci_h - hasilat)
        if not yardimci_gerekli else None,
    }


def istihdam_etki_analizi(
    yillik_hasilat: float,
    ek_hasilat: float,
    yillik_recete: float,
    ek_recete: float,
    ist_cfg: Dict,
    aylik_ikinci_maliyet: float,
    aylik_yardimci_maliyet: float,
    esik_carpani: float = 1.0,
) -> Dict:
    """Reçete hasılata eklenirse istihdam yükümlülüğü değişir mi, yıllık maliyeti ne?"""
    onceki = istihdam_durumu(yillik_hasilat, yillik_recete, ist_cfg, esik_carpani)
    sonraki = istihdam_durumu(yillik_hasilat + ek_hasilat,
                              yillik_recete + ek_recete, ist_cfg, esik_carpani)

    ek_ikinci = sonraki["ikinci_sayisi"] - onceki["ikinci_sayisi"]
    yardimci_eklendi = sonraki["yardimci_gerekli"] and not onceki["yardimci_gerekli"]

    yillik_maliyet = (ek_ikinci * aylik_ikinci_maliyet * 12.0
                      + (aylik_yardimci_maliyet * 12.0 if yardimci_eklendi else 0.0))
    return {
        "onceki": onceki,
        "sonraki": sonraki,
        "ek_ikinci_eczaci": ek_ikinci,
        "yardimci_eklendi": yardimci_eklendi,
        "yillik_ek_maliyet": yillik_maliyet,
    }


def barem_etki_analizi(
    yillik_hasilat: float,
    ek_hasilat: float,
    gelecek_sgk_tabi_ciro: float,
    yillik_recete_sayisi: float,
    cfg: Dict,
    buyume_orani: float = 0.0,
    esik_carpani: float = 1.0,
) -> Dict:
    """Bu yılın hasılatına ek_hasilat eklenirse GELECEK YIL ne kaybedilir?

    Args:
        yillik_hasilat: bu yıl sonu toplam hasılat projeksiyonu (reçete HARİÇ)
        ek_hasilat: değerlendirilen reçetenin/reçetelerin hasılata katkısı
        gelecek_sgk_tabi_ciro: gelecek yıl iskontoya TABİ SGK ciro tahmini
            (bu yılki değer; büyüme oranı burada uygulanır)
        yillik_recete_sayisi: gelecek yıl reçete adedi tahmini (hizmet bedeli için)
        buyume_orani: gelecek yıl büyüme/enflasyon katsayısı (0.10 = %10)

    Returns:
        {'onceki': barem_bilgi, 'sonraki': barem_bilgi,
         'barem_atladi': bool, 'hizmet_dustu': bool,
         'gelecek_ciro': float,
         'ek_iskonto_maliyeti': float,  # gelecek yıl ekstra iskonto (TL)
         'hizmet_bedeli_kaybi': float,  # gelecek yıl hizmet bedeli kaybı (TL)
         'toplam_gelecek_kayip': float}
    """
    onceki = barem_bilgi(yillik_hasilat, cfg, esik_carpani)
    sonraki = barem_bilgi(yillik_hasilat + ek_hasilat, cfg, esik_carpani)

    gelecek_ciro = gelecek_sgk_tabi_ciro * (1.0 + buyume_orani)
    gelecek_recete = yillik_recete_sayisi * (1.0 + buyume_orani)

    ek_iskonto = (sonraki["iskonto_orani"] - onceki["iskonto_orani"]) * gelecek_ciro
    hb_kayip = (onceki["hizmet_bedeli"] - sonraki["hizmet_bedeli"]) * gelecek_recete

    return {
        "onceki": onceki,
        "sonraki": sonraki,
        "barem_atladi": sonraki["iskonto_dilim"] > onceki["iskonto_dilim"],
        "hizmet_dustu": sonraki["hizmet_dilim"] > onceki["hizmet_dilim"],
        "gelecek_ciro": gelecek_ciro,
        "gelecek_recete_sayisi": gelecek_recete,
        "ek_iskonto_maliyeti": ek_iskonto,
        "hizmet_bedeli_kaybi": hb_kayip,
        "toplam_gelecek_kayip": ek_iskonto + hb_kayip,
    }


def tam_analiz(
    aylik_toplam_ciro: float,
    sgk_orani: float,
    aylik_recete_sayisi: float,
    recete_tutari: float,
    cfg: Dict,
    kurallar: Dict,
    alis: Optional[float] = None,
    karlilik_orani: Optional[float] = None,
    kan_urunu: bool = False,
    mobil_soguk: bool = False,
    aylik_tekrar: bool = False,
    iskonto_muaf_sgk_orani: float = 0.0,
    buyume_orani: float = 0.0,
    aylik_ikinci_maliyet: Optional[float] = None,
    aylik_yardimci_maliyet: Optional[float] = None,
    oda_katki_orani: float = 0.0,
    onceki_yil_hasilat: Optional[float] = None,
    barem_artis_orani: float = 0.0,
) -> Dict:
    """GUI'nin tek çağrıda kullandığı uçtan uca analiz.

    Args:
        aylik_toplam_ciro: aylık ortalama TOPLAM ciro (KDV hariç; nakit+SGK)
        sgk_orani: cironun SGK payı (0.70 = %70)
        aylik_recete_sayisi: aylık SGK reçete adedi
        recete_tutari: değerlendirilen reçetenin SGK'ya fatura tutarı
        alis / karlilik_orani: reçetenin depo ödemesi VEYA kârlılık oranı
        kan_urunu: depocu fiyatlı (kan ürünü/enzim) reçete → iskonto muaf
        aylik_tekrar: reçete her ay tekrarlanacaksa hasılata 12 katı eklenir
        iskonto_muaf_sgk_orani: SGK cironun halihazırda iskontodan muaf
            (kan ürünü vb.) kısmı — gelecek yıl iskonto tabanından düşülür
        buyume_orani: gelecek yıl ciro büyüme katsayısı
        onceki_yil_hasilat: kesintiye ESAS yılın hasılatı (örn. 2026'da 2024
            hasılatı — Medula 'Yeni İndirim Oranınız' mesajındaki tutar).
            Verilirse ŞU AN uygulanan iskonto/hizmet bedeli bundan hesaplanır
            (bugünkü baremlerle); verilmezse bu yıl projeksiyonu kullanılır.
        barem_artis_orani: gelecek dönem barem/eşik artış beklentisi (0.40 = %40).
            Bu yılın hasılatı GELECEKTE ilan edilecek (artırılmış) baremlerle
            kıyaslanır — barem atlama ve istihdam eşikleri bu çarpanla ölçeklenir.

    Zamanlama modeli (teyitli süreç): H yılı hasılatı → H+2 başında ilan edilen
    baremlerle oranlanır → H+1 Ekim'inden itibaren kesintilere RETRO uygulanır
    (fark ek faturayla mahsup). Örn. 2024 hasılatı + Mart 2026 baremleri →
    Ekim 2025'ten itibaren kesinti. Bugünkü reçete 2026 hasılatına girer,
    etkisi Ekim 2027+ kesintilerinde, o günün (artırılmış) baremleriyle görülür.
    """
    yillik_hasilat = aylik_toplam_ciro * 12.0
    yillik_sgk_ciro = yillik_hasilat * sgk_orani
    yillik_recete = aylik_recete_sayisi * 12.0
    sgk_tabi_ciro = yillik_sgk_ciro * (1.0 - iskonto_muaf_sgk_orani)

    # ŞU AN uygulanan kesinti: kesintiye esas yıl hasılatından (bugünkü baremler)
    mevcut = barem_bilgi(
        onceki_yil_hasilat if onceki_yil_hasilat else yillik_hasilat, cfg)
    carpan = kurallar.get("mobil_soguk_zincir_hizmet_carpani", 1.5)
    esik_carpani = 1.0 + barem_artis_orani

    kar = recete_kari(
        recete_tutari,
        alis=alis,
        karlilik_orani=karlilik_orani,
        iskontoya_tabi=not kan_urunu,
        iskonto_orani=mevcut["iskonto_orani"],
        hizmet_bedeli=mevcut["hizmet_bedeli"],
        mobil_soguk=mobil_soguk,
        hizmet_carpani=carpan,
        oda_katki_orani=oda_katki_orani,
    )

    ek_hasilat = recete_tutari * (12.0 if aylik_tekrar else 1.0)
    yillik_kar = kar["net_kar"] * (12.0 if aylik_tekrar else 1.0)

    # Reçete gelecek yılın iskonto tabanına yalnız DEVAM EDECEKSE girer:
    # tek seferlik reçete bu yılın hasılatını (barem belirleyici) büyütür ama
    # gelecek yıl cirosunda yoktur; aylık tekrarlıysa gelecek yıl da sürer.
    # Kan ürünü/enzim her durumda iskonto tabanı dışıdır.
    gelecek_taban = sgk_tabi_ciro + (
        ek_hasilat if (aylik_tekrar and not kan_urunu) else 0.0)

    etki = barem_etki_analizi(
        yillik_hasilat=yillik_hasilat,
        ek_hasilat=ek_hasilat,
        gelecek_sgk_tabi_ciro=gelecek_taban,
        yillik_recete_sayisi=yillik_recete,
        cfg=cfg,
        buyume_orani=buyume_orani,
        esik_carpani=esik_carpani,
    )

    # İkinci/yardımcı eczacı istihdam yükümlülüğü etkisi
    istihdam = None
    try:
        ist_cfg = istihdam_konfig(kurallar)
        if aylik_ikinci_maliyet is None or aylik_yardimci_maliyet is None:
            varsayilan = istihdam_varsayilan_maliyetler(kurallar)
            if aylik_ikinci_maliyet is None:
                aylik_ikinci_maliyet = varsayilan["ikinci"]["aylik_toplam"]
            if aylik_yardimci_maliyet is None:
                aylik_yardimci_maliyet = varsayilan["yardimci"]["aylik_toplam"]
        ikinci_m = aylik_ikinci_maliyet
        yardimci_m = aylik_yardimci_maliyet
        istihdam = istihdam_etki_analizi(
            yillik_hasilat=yillik_hasilat,
            ek_hasilat=ek_hasilat,
            yillik_recete=yillik_recete,
            ek_recete=12.0 if aylik_tekrar else 1.0,
            ist_cfg=ist_cfg,
            aylik_ikinci_maliyet=ikinci_m,
            aylik_yardimci_maliyet=yardimci_m,
            esik_carpani=esik_carpani,
        )
    except KeyError:
        logger.warning("İstihdam kriterleri konfigürasyonu bulunamadı — atlandı")

    istihdam_maliyet = istihdam["yillik_ek_maliyet"] if istihdam else 0.0

    return {
        "aylik_tekrar": aylik_tekrar,
        "onceki_yil_hasilat": onceki_yil_hasilat,
        "esik_carpani": esik_carpani,
        "yillik_hasilat": yillik_hasilat,
        "yillik_sgk_ciro": yillik_sgk_ciro,
        "sgk_tabi_ciro": sgk_tabi_ciro,
        "yillik_recete_sayisi": yillik_recete,
        "mevcut_barem": mevcut,
        "recete_kar": kar,
        "ek_hasilat": ek_hasilat,
        "recete_yillik_kar": yillik_kar,
        "etki": etki,
        "istihdam": istihdam,
        "net_sonuc": yillik_kar - etki["toplam_gelecek_kayip"] - istihdam_maliyet,
    }
