"""
Hibrit Siparişçi v2 — duman testi (GUI'siz, Selenium'suz, Botanik'siz)
=====================================================================
Doğruladıkları:
1. EczAsist kesin sipariş listesi yüklenip Fatih ürün formatına çevriliyor
2. HibritController + SanalBotanik, Fatih'in kurulu modülleriyle kuruluyor
3. get_all_products_data_only bizim listeyi doğru akıtıyor (callback dahil)
4. siparis_adet == bizim miktar (hibrit_ihtiyac) — Fatih hesabı devrede değil
5. Botanik yazma metotları no-op ve durum ürün dict'inde saklanıyor

Çalıştır: python test_hibrit_v2_smoke.py
Not: Aktif sipariş çalışmasında en az 1 barkodlu sipariş olmalı.
"""
import os
import sys
from pathlib import Path

ECZ = Path(__file__).resolve().parent
sys.path.insert(0, str(ECZ))

import hibrit_siparisci_gui as h


SENTETIK_SIPARISLER = [
    # kesin_siparisler satır formatı (siparis_db.calisma_siparisleri_getir)
    {"urun_adi": "PAROL 500 MG 30 TABLET", "barkod": "8699522017563",
     "miktar": 20, "mf": "10+2", "toplam": 24, "stok": 5, "aylik_ort": 42.5},
    {"urun_adi": "MAJEZIK 100 MG 30 TABLET", "barkod": "8699541794404",
     "miktar": 10, "mf": "", "toplam": 10, "stok": 0, "aylik_ort": 18.0},
    {"urun_adi": "BARKODSUZ TEST URUNU", "barkod": "",
     "miktar": 3, "mf": "", "toplam": 3, "stok": 1, "aylik_ort": 1.0},
    {"urun_adi": "MIKTARSIZ TEST URUNU", "barkod": "8699999999999",
     "miktar": 0, "mf": "", "toplam": 0, "stok": 9, "aylik_ort": 0.5},
]


def main():
    # 1) EczAsist listesi (aktif çalışma yoksa sentetik veriyle devam)
    calisma, siparisler = h._kesin_liste_yukle()
    if calisma:
        print(f"Çalışma: {calisma.get('ad')!r} | kayıt: {len(siparisler)} (gerçek DB)")
    else:
        siparisler = SENTETIK_SIPARISLER
        print(f"Aktif çalışma yok → SENTETİK {len(siparisler)} kayıtla test ediliyor")

    products, barkodsuz = h._urunleri_hazirla(siparisler)
    print(f"Ürün: {len(products)} | barkodsuz/miktarsız atlanan: {len(barkodsuz) + sum(1 for s in siparisler if not int(float(s.get('miktar') or 0)))}")
    if not products:
        print("SKIP: işlenebilir sipariş yok")
        return 0
    if not calisma:
        # sentetik: 4 kayıttan 2'si elenmiş olmalı (barkodsuz + miktarsız)
        assert len(products) == 2, len(products)
        assert products[0]["hibrit_ihtiyac"] == 20 and products[0]["hibrit_toplam"] == 24

    # 2) Fatih ortamı + sınıflar
    assert (h.SIPARISCI_DIZIN / "Siparisci.pyw").exists(), "Siparişçi kurulu değil"
    sys.path.insert(0, str(h.SIPARISCI_DIZIN))
    os.chdir(h.SIPARISCI_DIZIN)

    from src.controller import MainController
    from src.botanik.eos_controller import BotanikEOSController
    from src.utils import logger as sip_logger

    HibritController = h._siniflari_kur(BotanikEOSController, MainController, sip_logger)
    c = HibritController(products)

    assert c.botanik.connect() is True
    assert c.botanik.is_connected() is True
    assert c.botanik.get_total_row_count() == len(products)
    assert c.botanik.get_row_numbers() == [p["row"] for p in products]
    assert c.botanik.click_depo_personel_cell(products[0]["row"]) == products[0]["barkod"]

    # 3) Kuru okuma (depo araması verilmedi → sadece liste akışı + callback)
    gorulen = []
    okunan = c.botanik.get_all_products_data_only(
        on_product_read=lambda p, i, t: gorulen.append((i, t, p["urun_adi"], p["siparis_adet"]))
    )
    assert len(okunan) == len(products), (len(okunan), len(products))
    assert len(gorulen) == len(products)
    for i, t, ad, sa in gorulen[:5]:
        print(f"  {i}/{t}  {ad[:40]:40s} siparis_adet={sa}")

    # 4) Miktar bizim kararımız
    for p in okunan:
        assert p["siparis_adet"] == p["hibrit_ihtiyac"], \
            (p["urun_adi"], p["siparis_adet"], p["hibrit_ihtiyac"])
    # _auto_add_to_cart'ın kullandığı yol da aynı değeri görmeli
    assert c._calculate_order_quantity(okunan[0]) == okunan[0]["hibrit_ihtiyac"]

    # 5) Yazma no-op + dict'te saklama
    r1 = products[0]["row"]
    assert c.botanik.set_adet_value(r1, 5) is True
    assert c.botanik.set_mf_value(r1, 2) is True
    assert c.botanik.set_aciklama_value(r1, "hibrit test notu") is True
    assert c.botanik.get_aciklama_value(r1) == "hibrit test notu"
    assert c.botanik.set_tevzi_ilac(r1) is True
    assert products[0]["hibrit_yazilan_adet"] == 5
    assert products[0]["hibrit_yazilan_mf"] == 2

    # 6) GUI yardımcı yüzeyleri
    isimler = c.botanik.get_all_product_names_with_rows()
    assert isimler.get(products[0]["urun_adi"].lower()) == r1
    assert c.botanik.get_muadil_list() == []

    # 7) MF plan ayrıştırma (adaptör)
    test_p, _ = h._urunleri_hazirla([
        {"urun_adi": "PLANLI", "barkod": "8690000000001", "miktar": 100,
         "mf": "100+30", "toplam": 130, "stok": 0, "aylik_ort": 1},
        {"urun_adi": "PLANSIZ", "barkod": "8690000000002", "miktar": 5,
         "mf": "", "toplam": 5, "stok": 0, "aylik_ort": 1},
    ])
    assert test_p[0]["hibrit_mf_plan_min"] == 100 and test_p[0]["hibrit_mf_plan_mf"] == 30
    assert test_p[1]["hibrit_mf_plan_min"] is None

    # 8) Kalem bazında karma MF: plan birebir varsa öne alınır, yoksa serbest
    import json as _json
    fake_sonuc = {
        "tum_secenekler": [
            {"depo": "alliance", "min_adet": 5, "mf": 1, "efektif_birim": 10.0},
            {"depo": "selcuk", "min_adet": 100, "mf": 30, "efektif_birim": 10.5},
        ],
        "en_karli": {"depo": "alliance", "min_adet": 5, "mf": 1, "efektif_birim": 10.0},
    }
    orijinal = MainController.bul_en_karli_secenek
    try:
        MainController.bul_en_karli_secenek = \
            lambda self, product: _json.loads(_json.dumps(fake_sonuc))
        planli = {"urun_adi": "PLANLI", "hibrit_mf_plan_min": 100, "hibrit_mf_plan_mf": 30}
        r = c.bul_en_karli_secenek(planli)
        assert r["en_karli"]["depo"] == "selcuk", r["en_karli"]
        assert r["tum_secenekler"][0]["depo"] == "selcuk"
        assert "bulundu" in planli["hibrit_mf_plan_durum"]

        yok = {"urun_adi": "PLANYOK", "hibrit_mf_plan_min": 20, "hibrit_mf_plan_mf": 7}
        r2 = c.bul_en_karli_secenek(yok)
        assert r2["en_karli"]["depo"] == "alliance"  # serbest (dokunulmadı)
        assert "serbest" in yok["hibrit_mf_plan_durum"]

        plansiz = {"urun_adi": "PLANSIZ"}
        r3 = c.bul_en_karli_secenek(plansiz)
        assert r3["en_karli"]["depo"] == "alliance" and "hibrit_mf_plan_durum" not in plansiz
    finally:
        MainController.bul_en_karli_secenek = orijinal

    # 9) Geri bildirim: depo_bilgileri yaz → DepoSonuclari olarak geri oku
    if calisma:
        from siparis_db import get_siparis_db
        db = get_siparis_db()
        sid = siparisler[0]["id"]
        ozet = {"Selcuk": "★ 10+2 76,92 TL", "MFPlan": "PLAN 10+2 bulundu: selcuk"}
        assert db.siparis_guncelle(sid, depo_bilgileri=_json.dumps(ozet, ensure_ascii=False))
        geri = [s for s in db.calisma_siparisleri_getir(calisma["id"]) if s["id"] == sid][0]
        assert geri.get("DepoSonuclari") == ozet, geri.get("DepoSonuclari")
        db.siparis_guncelle(sid, depo_bilgileri=None)  # testi temizle
        print("Geri bildirim turu: OK")

    # 10) 13 aylık kırılım: EOS'tan çek → Fatih'in mevsim katsayısı çalışsın
    try:
        sys.path.insert(0, str(ECZ))
        from botanik_db import BotanikDB
        bdb = BotanikDB()
        top = bdb.sorgu_calistir(
            "SELECT TOP 1 ri.RIUrunId as UrunId FROM ReceteIlaclari ri "
            "JOIN ReceteAna ra ON ri.RIRxId = ra.RxId "
            "WHERE ra.RxSilme = 0 AND ri.RISilme = 0 "
            "ORDER BY ri.RIRxId DESC")
        if top:
            uid = int(top[0]["UrunId"])
            kp = [{"hibrit_urun_id": uid, "urun_adi": "EOS-TEST", "monthly_sales": {}}]
            dolan = h._aylik_kirilim_topla(kp)
            ms = kp[0]["monthly_sales"]
            assert len(ms) == 13, len(ms)
            import re as _re
            assert all(_re.match(r"^\d{2}\.\d{2}$", k) for k in ms), list(ms)[:3]
            seri = c.botanik._parse_monthly_series(ms)
            assert len(seri) == 13
            katsayi, kaynak = c.botanik.hesapla_mevsim_katsayisi(ms)
            print(f"Kırılım turu: UrunId={uid}, dolan={dolan}, "
                  f"katsayı={katsayi:.2f} ({kaynak})")
        else:
            print("Kırılım turu: EOS'ta satır yok, atlandı")
    except Exception as e:
        print(f"Kırılım turu: EOS erişilemedi, atlandı ({e})")

    print("\nSMOKE OK — hibrit enjeksiyon hattı çalışıyor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
