# -*- coding: utf-8 -*-
"""SGK Barem motoru akıl testleri (2026/1 Ek Protokol değerleriyle)."""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import sgk_barem_motoru as m

kurallar = m.kurallari_yukle()
cfg = m.yil_konfig(kurallar, "2026")

BASARI = []
HATA = []


def kontrol(ad, kosul, detay=""):
    if kosul:
        BASARI.append(ad)
        print(f"  PASS {ad}")
    else:
        HATA.append(ad)
        print(f"  FAIL {ad} {detay}")


print("== 1) İskonto barem sınırları ==")
b = m.barem_bilgi(7_399_182, cfg)
kontrol("7.399.182 TL tam sınır → %0 (1. dilim)", b["iskonto_orani"] == 0.0 and b["iskonto_dilim"] == 0)
b = m.barem_bilgi(7_399_183, cfg)
kontrol("7.399.183 TL → %0,50 (2. dilim)", abs(b["iskonto_orani"] - 0.005) < 1e-9)
b = m.barem_bilgi(20_000_000, cfg)
kontrol("20M TL → %2,25 (son dilim)", abs(b["iskonto_orani"] - 0.0225) < 1e-9)
kontrol("son dilimde bareme_kalan None", b["iskonto_bareme_kalan"] is None)
b = m.barem_bilgi(7_000_000, cfg)
kontrol("7M → üst esige 399.182 kaldı", abs(b["iskonto_bareme_kalan"] - 399_182) < 1)

print("== 2) Hizmet bedeli dilimleri (7 dilim) ==")
b = m.barem_bilgi(4_000_000, cfg)
kontrol("4M → 29,85 TL", abs(b["hizmet_bedeli"] - 29.85) < 1e-9)
b = m.barem_bilgi(5_000_000, cfg)
kontrol("5M → 20,09 TL (iskonto hâlâ %0)", abs(b["hizmet_bedeli"] - 20.09) < 1e-9 and b["iskonto_orani"] == 0.0)
b = m.barem_bilgi(10_000_000, cfg)
kontrol("10M → 12,84 TL + iskonto %1,05", abs(b["hizmet_bedeli"] - 12.84) < 1e-9 and abs(b["iskonto_orani"] - 0.0105) < 1e-9)

print("== 3) Kademeli kâr (kümülatif, Karar 11031) ==")
dl = kurallar["kademeli_kar"]["dilimler"]
kontrol("DSF 100 → eczacı 28,00", abs(m.kademeli_kar(100, dl) - 28.0) < 0.01)
beklenen = 440.65 * 0.28 + (500 - 440.65) * 0.18  # 134.065
kontrol("DSF 500 → eczacı 134,07 (kümülatif)", abs(m.kademeli_kar(500, dl) - beklenen) < 0.01)
beklenen = 440.65 * 0.28 + (882.66 - 440.65) * 0.18 + (100_000 - 882.66) * 0.13
kontrol("DSF 100.000 → marjinal %13 dilimi", abs(m.kademeli_kar(100_000, dl) - beklenen) < 0.01)
kontrol("DSF 500 → depocu 38,81", abs(m.kademeli_kar(500, dl, "depocu") - (440.65 * 0.08 + 59.35 * 0.06)) < 0.01)

print("== 4) Reçete kârı ==")
k = m.recete_kari(10_000, alis=9_000, iskontoya_tabi=True, iskonto_orani=0.0105, hizmet_bedeli=12.84)
kontrol("normal reçete: 1000 - 105 + 12,84", abs(k["net_kar"] - (1000 - 105 + 12.84)) < 0.01)
k = m.recete_kari(400_000, karlilik_orani=0.06, iskontoya_tabi=False, iskonto_orani=0.0225, hizmet_bedeli=11.65)
kontrol("kan ürünü: iskonto kesilmez", k["iskonto_kesintisi"] == 0.0 and abs(k["net_kar"] - (24_000 + 11.65)) < 0.01)
k = m.recete_kari(1_000, alis=900, iskonto_orani=0.0, hizmet_bedeli=20.09, mobil_soguk=True)
kontrol("mobil/soğuk: hizmet bedeli x1,5", abs(k["hizmet_bedeli"] - 30.135) < 0.001)

print("== 5) Barem etki analizi ==")
# Atlamayan: 6M + 100k = 6.1M hâlâ 1. iskonto dilimi VE aynı hizmet dilimi (4.44-7.40M)
e = m.barem_etki_analizi(6_000_000, 100_000, 4_000_000, 10_000, cfg)
kontrol("atlama yok → kayıp 0", e["toplam_gelecek_kayip"] == 0.0 and not e["barem_atladi"])
# Atlayan: 7.3M + 400k = 7.7M → iskonto %0→%0,50 VE hizmet 20,09→16,71
e = m.barem_etki_analizi(7_300_000, 400_000, 5_000_000, 10_800, cfg)
kontrol("iskonto atladı", e["barem_atladi"])
kontrol("ek iskonto = 0,005 x 5M = 25.000", abs(e["ek_iskonto_maliyeti"] - 25_000) < 0.01)
kontrol("hizmet kaybı = 3,38 x 10.800 = 36.504", abs(e["hizmet_bedeli_kaybi"] - (20.09 - 16.71) * 10_800) < 0.01)
# Büyüme katsayısı taban ve reçete sayısını büyütür
e2 = m.barem_etki_analizi(7_300_000, 400_000, 5_000_000, 10_800, cfg, buyume_orani=0.10)
kontrol("büyüme %10 → ek iskonto 27.500", abs(e2["ek_iskonto_maliyeti"] - 27_500) < 0.01)

print("== 6) Uçtan uca: 400k kan ürünü reçetesi barem atlatıyor ==")
# Aylık 600k ciro, %70 SGK, 900 reçete/ay → yıllık 7,2M (1. dilim, %0)
s = m.tam_analiz(
    aylik_toplam_ciro=600_000, sgk_orani=0.70, aylik_recete_sayisi=900,
    recete_tutari=400_000, cfg=cfg, kurallar=kurallar,
    karlilik_orani=0.06, kan_urunu=True)
kontrol("mevcut: %0 iskonto", s["mevcut_barem"]["iskonto_orani"] == 0.0)
kontrol("reçete iskonto muaf", s["recete_kar"]["iskonto_kesintisi"] == 0.0)
kontrol("7,2M+400k=7,6M → barem atlar", s["etki"]["barem_atladi"])
# Kan ürünü gelecek yıl iskonto tabanına GİRMEZ: taban = 7,2M x 0,7 = 5,04M
kontrol("gelecek taban 5,04M (kan ürünü hariç)", abs(s["etki"]["gelecek_ciro"] - 5_040_000) < 1)
beklenen_kayip = 0.005 * 5_040_000 + (20.09 - 16.71) * 10_800
kontrol("toplam kayıp = 25.200 + 36.504", abs(s["etki"]["toplam_gelecek_kayip"] - beklenen_kayip) < 0.01)
kontrol("net sonuç NEGATİF (reçete kârı 24k < kayıp 61,7k)", s["net_sonuc"] < 0)

print("== 7) Normal ilaç: tek seferlik tabana GİRMEZ, aylık tekrar GİRER ==")
s2 = m.tam_analiz(
    aylik_toplam_ciro=600_000, sgk_orani=0.70, aylik_recete_sayisi=900,
    recete_tutari=400_000, cfg=cfg, kurallar=kurallar,
    alis=340_000, kan_urunu=False)
kontrol("normal reçete iskontoya tabi (bu yıl %0 kesinti)", s2["recete_kar"]["iskonto_kesintisi"] == 0.0)
kontrol("tek seferlik: gelecek taban 5,04M (reçete HARİÇ)", abs(s2["etki"]["gelecek_ciro"] - 5_040_000) < 1)
s2b = m.tam_analiz(
    aylik_toplam_ciro=600_000, sgk_orani=0.70, aylik_recete_sayisi=900,
    recete_tutari=100_000, cfg=cfg, kurallar=kurallar,
    alis=85_000, kan_urunu=False, aylik_tekrar=True)
kontrol("aylık tekrar: gelecek taban 5,04M + 1,2M", abs(s2b["etki"]["gelecek_ciro"] - 6_240_000) < 1)

print("== 8) Aylık tekrar: 12 katı hasılat ==")
s3 = m.tam_analiz(
    aylik_toplam_ciro=600_000, sgk_orani=0.70, aylik_recete_sayisi=900,
    recete_tutari=100_000, cfg=cfg, kurallar=kurallar,
    karlilik_orani=0.06, kan_urunu=True, aylik_tekrar=True)
kontrol("ek hasılat 1,2M", abs(s3["ek_hasilat"] - 1_200_000) < 0.01)
kontrol("yıllık kâr = 12 x tek reçete kârı", abs(s3["recete_yillik_kar"] - 12 * s3["recete_kar"]["net_kar"]) < 0.01)

print("== 9) İstihdam durumu (2025 kriterleri: ikinci 49.906.075 TL / 80k reçete, yardımcı 23.664.692 TL) ==")
ist_cfg = m.istihdam_konfig(kurallar)
d = m.istihdam_durumu(20_000_000, 30_000, ist_cfg)
kontrol("20M/30k reçete → yükümlülük yok", d["ikinci_sayisi"] == 0 and not d["yardimci_gerekli"])
d = m.istihdam_durumu(25_000_000, 30_000, ist_cfg)
kontrol("25M → yardımcı GEREKLİ, ikinci yok", d["yardimci_gerekli"] and d["ikinci_sayisi"] == 0)
d = m.istihdam_durumu(50_000_000, 30_000, ist_cfg)
kontrol("50M → 1 ikinci eczacı", d["ikinci_sayisi"] == 1)
d = m.istihdam_durumu(100_000_000, 30_000, ist_cfg)
kontrol("100M → 2 ikinci eczacı (2. kat)", d["ikinci_sayisi"] == 2)
d = m.istihdam_durumu(200_000_000, 30_000, ist_cfg)
kontrol("200M → azami 3 ikinci eczacı", d["ikinci_sayisi"] == 3)
d = m.istihdam_durumu(20_000_000, 85_000, ist_cfg)
kontrol("85k reçete → hasılat düşük olsa da 1 ikinci eczacı", d["ikinci_sayisi"] == 1)
d = m.istihdam_durumu(23_000_000, 10_000, ist_cfg)
kontrol("yardımcı eşiğine 664.692 kaldı", abs(d["yardimci_esige_kalan"] - 664_692) < 1)

print("== 9b) Yönetmelik m.16 'aşılması' sınır testleri ==")
d = m.istihdam_durumu(49_906_075, 30_000, ist_cfg)
kontrol("TAM eşikte (49.906.075) ikinci eczacı GEREKMEZ (aşılmadı)", d["ikinci_sayisi"] == 0)
d = m.istihdam_durumu(49_906_076, 30_000, ist_cfg)
kontrol("eşik + 1 TL → 1 ikinci eczacı", d["ikinci_sayisi"] == 1)
d = m.istihdam_durumu(99_812_150, 30_000, ist_cfg)
kontrol("TAM 2x eşikte → hâlâ 1 (2. kat aşılmadı)", d["ikinci_sayisi"] == 1)
d = m.istihdam_durumu(23_664_692, 10_000, ist_cfg)
kontrol("TAM yardımcı eşiğinde yardımcı GEREKMEZ", not d["yardimci_gerekli"])
d = m.istihdam_durumu(23_664_693, 10_000, ist_cfg)
kontrol("yardımcı eşiği + 1 TL → GEREKLİ", d["yardimci_gerekli"])
d = m.istihdam_durumu(20_000_000, 80_000, ist_cfg)
kontrol("TAM 80.000 reçetede ikinci eczacı GEREKMEZ", d["ikinci_sayisi"] == 0)
d = m.istihdam_durumu(20_000_000, 80_001, ist_cfg)
kontrol("80.001 reçete → 1 ikinci eczacı", d["ikinci_sayisi"] == 1)

print("== 10) İstihdam etki analizi ==")
e = m.istihdam_etki_analizi(49_800_000, 400_000, 40_000, 1, ist_cfg,
                            aylik_ikinci_maliyet=75_302.46,
                            aylik_yardimci_maliyet=39_882.25)
kontrol("49,8M + 400k → ikinci eczacı yükümlülüğü doğar", e["ek_ikinci_eczaci"] == 1)
kontrol("yıllık maliyet = 75.302,46 x 12", abs(e["yillik_ek_maliyet"] - 75_302.46 * 12) < 0.01)
e = m.istihdam_etki_analizi(23_500_000, 400_000, 40_000, 1, ist_cfg,
                            aylik_ikinci_maliyet=75_302.46,
                            aylik_yardimci_maliyet=39_882.25)
kontrol("23,5M + 400k → yardımcı eczacı yükümlülüğü doğar", e["yardimci_eklendi"])
kontrol("yıllık maliyet = 39.882,25 x 12", abs(e["yillik_ek_maliyet"] - 39_882.25 * 12) < 0.01)
e = m.istihdam_etki_analizi(10_000_000, 400_000, 40_000, 1, ist_cfg,
                            aylik_ikinci_maliyet=75_302.46,
                            aylik_yardimci_maliyet=39_882.25)
kontrol("eşiklerden uzak → istihdam etkisi 0", e["yillik_ek_maliyet"] == 0.0)

print("== 11) tam_analiz istihdam entegrasyonu ==")
# Aylık 1,96M ciro → yıllık 23,52M: 400k reçete yardımcı eczacı eşiğini (23,664M) aşırtır
s9 = m.tam_analiz(
    aylik_toplam_ciro=1_960_000, sgk_orani=0.70, aylik_recete_sayisi=2_000,
    recete_tutari=400_000, cfg=cfg, kurallar=kurallar,
    karlilik_orani=0.06, kan_urunu=True)
kontrol("istihdam sonucu dolu", s9["istihdam"] is not None)
kontrol("yardımcı eczacı yükümlülüğü doğdu", s9["istihdam"]["yardimci_eklendi"])
kontrol("net_sonuc istihdam maliyetini düşüyor",
        s9["net_sonuc"] < s9["recete_yillik_kar"] - s9["etki"]["toplam_gelecek_kayip"])
beklenen_net = (s9["recete_yillik_kar"] - s9["etki"]["toplam_gelecek_kayip"]
                - s9["istihdam"]["yillik_ek_maliyet"])
kontrol("net_sonuc = kâr − barem kaybı − istihdam", abs(s9["net_sonuc"] - beklenen_net) < 0.01)

print("== 12) Fiyat → kârlılık eğrisi ==")
dl = kurallar["kademeli_kar"]["dilimler"]
tablo = m.fiyat_karlilik_tablosu([100, 500, 1000, 100_000], dl)
kontrol("DSF 100: kâr 28, kâr/alış %28", abs(tablo[0]["kar"] - 28) < 0.01 and abs(tablo[0]["kar_alis_orani"] - 0.28) < 1e-9)
kontrol("DSF 100: kâr/satış %21,875", abs(tablo[0]["kar_satis_orani"] - 28 / 128) < 1e-9)
kontrol("DSF 500: kâr/alış ~%26,8 (kademe etkisi başladı)", 0.265 < tablo[1]["kar_alis_orani"] < 0.27)
beklenen_kar_1000 = 440.65 * 0.28 + (882.66 - 440.65) * 0.18 + (1000 - 882.66) * 0.13
kontrol("DSF 1.000: kümülatif kâr doğru", abs(tablo[2]["kar"] - beklenen_kar_1000) < 0.01)
kontrol("DSF 100.000: kâr/alış %13'e yakınsıyor", 0.13 < tablo[3]["kar_alis_orani"] < 0.132)
kontrol("marjinal dilimler: %28 → %18 → %13",
        tablo[0]["marjinal_oran"] == 0.28 and tablo[1]["marjinal_oran"] == 0.18
        and tablo[3]["marjinal_oran"] == 0.13)
kontrol("kârlılık fiyatla monoton AZALIYOR",
        tablo[0]["kar_alis_orani"] > tablo[1]["kar_alis_orani"] > tablo[2]["kar_alis_orani"] > tablo[3]["kar_alis_orani"])

print("== 13) Personel TAM maliyet (2026: asgari brüt 33.030, işveren çarpanı 1,2175) ==")
mp = kurallar["istihdam"]["maliyet_parametreleri"]
# İkinci eczacı: brüt 3x = 99.090
pm = m.personel_tam_maliyet(99_090, mp, fazla_mesai=False, yemek=False)
kontrol("ikinci: salt ücret maliyeti 99.090 x 1,2175 = 120.642,08", abs(pm["aylik_toplam"] - 120_642.075) < 0.01)
pm = m.personel_tam_maliyet(99_090, mp, fazla_mesai=True, yemek=True)
kontrol("ikinci: FM brüt = brütün %15'i (270sa/yıl, x1,5)", abs(pm["fazla_mesai_brut"] - 99_090 * 0.15) < 0.01)
kontrol("ikinci: yemek 300 x 26 = 7.800", abs(pm["yemek_tutari"] - 7_800) < 0.01)
beklenen = 99_090 * 1.2175 + 99_090 * 0.15 * 1.2175 + 7_800
kontrol("ikinci: TAM maliyet 146.538,39/ay", abs(pm["aylik_toplam"] - beklenen) < 0.01 and abs(beklenen - 146_538.39) < 0.5)
# Yardımcı eczacı: brüt 1,5x = 49.545
vm = m.istihdam_varsayilan_maliyetler(kurallar)
kontrol("yardımcı: TAM maliyet 77.169,20/ay",
        abs(vm["yardimci"]["aylik_toplam"] - (49_545 * 1.2175 * 1.15 + 7_800)) < 0.01)
kontrol("varsayılanlar: ikinci > yardımcı", vm["ikinci"]["aylik_toplam"] > vm["yardimci"]["aylik_toplam"])

print("== 14) tam_analiz varsayılan maliyet = TAM işveren maliyeti ==")
s14 = m.tam_analiz(
    aylik_toplam_ciro=1_960_000, sgk_orani=0.70, aylik_recete_sayisi=2_000,
    recete_tutari=400_000, cfg=cfg, kurallar=kurallar,
    karlilik_orani=0.06, kan_urunu=True)
kontrol("yardımcı yükümlülüğü doğdu (23,52M+400k)", s14["istihdam"]["yardimci_eklendi"])
kontrol("istihdam maliyeti = yardımcı TAM maliyet x 12",
        abs(s14["istihdam"]["yillik_ek_maliyet"] - vm["yardimci"]["aylik_toplam"] * 12) < 0.01)

print("== 15) Oda katkı payı (sıralı dağıtım) ==")
k = m.recete_kari(400_000, karlilik_orani=0.04, iskontoya_tabi=False,
                  iskonto_orani=0.0225, hizmet_bedeli=11.65, oda_katki_orani=0.005)
kontrol("400k kan ürünü: oda payı = 2.000 TL", abs(k["oda_katki_payi"] - 2_000) < 0.01)
kontrol("net kâr = 16.000 − 2.000 + 11,65", abs(k["net_kar"] - (16_000 - 2_000 + 11.65)) < 0.01)
k2 = m.recete_kari(400_000, karlilik_orani=0.04, iskontoya_tabi=False,
                   iskonto_orani=0.0225, hizmet_bedeli=11.65)
kontrol("oran verilmezse oda payı 0 (geriye uyum)", k2["oda_katki_payi"] == 0.0)
s15 = m.tam_analiz(
    aylik_toplam_ciro=1_960_000, sgk_orani=0.70, aylik_recete_sayisi=2_000,
    recete_tutari=400_000, cfg=cfg, kurallar=kurallar,
    karlilik_orani=0.04, kan_urunu=True, oda_katki_orani=0.005)
kontrol("tam_analiz oda payını kârdan düşüyor",
        abs(s15["recete_kar"]["net_kar"] - (16_000 - 2_000 + 11.65)) < 0.01)

print("== 16) Zamanlama modeli: esas yıl + barem artış çarpanı ==")
# Kullanıcının GERÇEK Medula senaryosu: 2024 hasılatı 8.087.782,66 → %0,5 olmalı
b = m.barem_bilgi(8_087_782.66, cfg)
kontrol("Medula doğrulama: 8.087.782,66 → %0,50", abs(b["iskonto_orani"] - 0.005) < 1e-9)
# Çarpanlı eşik: 12M hasılat bugünkü baremde 4. dilim (%1,35), +%40 artmış baremde 3. dilim (%1,05)
b0 = m.barem_bilgi(12_000_000, cfg)
b1 = m.barem_bilgi(12_000_000, cfg, esik_carpani=1.40)
kontrol("12M bugünkü baremde %1,35", abs(b0["iskonto_orani"] - 0.0135) < 1e-9)
kontrol("12M +%40 baremde %0,50 (iki dilim aşağı: 12M/1,4=8,57M bandı)", abs(b1["iskonto_orani"] - 0.005) < 1e-9)
kontrol("çarpanlı bareme_kalan ölçekli (9.248.976x1,4 - 12M)", abs(b1["iskonto_bareme_kalan"] - (9_248_976 * 1.40 - 12_000_000)) < 1)
# İstihdam eşiği çarpanla: 50M bugünkü eşiği aşar, +%40'lı eşiği (69,87M) aşmaz
d0 = m.istihdam_durumu(50_000_000, 30_000, m.istihdam_konfig(kurallar))
d1 = m.istihdam_durumu(50_000_000, 30_000, m.istihdam_konfig(kurallar), esik_carpani=1.40)
kontrol("50M bugünkü eşikte 1 ikinci eczacı", d0["ikinci_sayisi"] == 1)
kontrol("50M gelecek (+%40) eşikte 0", d1["ikinci_sayisi"] == 0)
kontrol("reçete eşiği (80.000) çarpandan etkilenmez",
        m.istihdam_durumu(1_000_000, 80_001, m.istihdam_konfig(kurallar), esik_carpani=1.40)["ikinci_sayisi"] == 1)

print("== 17) tam_analiz: onceki_yil_hasilat + barem_artis_orani ==")
# Esas yıl 8.087.782 (%0,5 kesiliyor) ama bu yıl projeksiyonu 14M olan eczane
s17 = m.tam_analiz(
    aylik_toplam_ciro=1_166_667, sgk_orani=0.70, aylik_recete_sayisi=1_500,
    recete_tutari=100_000, cfg=cfg, kurallar=kurallar, alis=88_000,
    onceki_yil_hasilat=8_087_782.66, barem_artis_orani=0.40)
kontrol("reçeteye BUGÜN kesilen iskonto esas yıldan (%0,5)",
        abs(s17["recete_kar"]["iskonto_kesintisi"] - 100_000 * 0.005) < 0.01)
kontrol("hizmet bedeli de esas yıldan (16,71 TL)",
        abs(s17["recete_kar"]["hizmet_bedeli"] - 16.71) < 0.01)
kontrol("gelecek kıyas çarpanlı eşiklerle (14M/1,4=10M bandı → %1,05 dilimi)",
        abs(s17["etki"]["onceki"]["iskonto_orani"] - 0.0105) < 1e-9)
# Aynı senaryo çarpansız: 14M bugünkü baremde %1,35 dilimi olurdu
s17b = m.tam_analiz(
    aylik_toplam_ciro=1_166_667, sgk_orani=0.70, aylik_recete_sayisi=1_500,
    recete_tutari=100_000, cfg=cfg, kurallar=kurallar, alis=88_000,
    onceki_yil_hasilat=8_087_782.66, barem_artis_orani=0.0)
kontrol("çarpansız gelecek kıyas %1,35 (fark barem artışından)",
        abs(s17b["etki"]["onceki"]["iskonto_orani"] - 0.0135) < 1e-9)
kontrol("geriye uyum: parametresiz çağrı eski davranış",
        m.tam_analiz(aylik_toplam_ciro=600_000, sgk_orani=0.7, aylik_recete_sayisi=900,
                     recete_tutari=400_000, cfg=cfg, kurallar=kurallar,
                     karlilik_orani=0.06, kan_urunu=True)["mevcut_barem"]["iskonto_orani"] == 0.0)

print()
print(f"SONUÇ: {len(BASARI)} PASS, {len(HATA)} FAIL")
if HATA:
    print("Başarısız:", HATA)
    sys.exit(1)
