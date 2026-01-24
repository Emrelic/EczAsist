# -*- coding: utf-8 -*-
"""
AUGMENTIN 1000MG 14 icin fiyat farki bul
"""
import sys
sys.path.insert(0, '.')
from botanik_db import BotanikDB

def main():
    db = BotanikDB()
    if not db.baglan():
        print("Veritabanina baglanilamadi!")
        return

    urun_id = 2766  # AUGMENTIN-BID 1000MG 14 FILM TABLET
    esdeger_id = 105

    print("=" * 80)
    print("AUGMENTIN 1000MG 14 - FIYAT FARKI ARASTIRMASI")
    print(f"UrunId: {urun_id}, EsdegerId: {esdeger_id}")
    print("=" * 80)

    # EsdegerListesi tablosu
    print("\n--- EsdegerListesi ---")
    try:
        sql = f"SELECT * FROM EsdegerListesi WHERE EsdegerId = {esdeger_id}"
        sonuc = db.sorgu_calistir(sql)
        if sonuc:
            for k, v in sonuc[0].items():
                print(f"  {k} = {v}")
    except Exception as e:
        print(f"  Hata: {e}")

    # SGKKod tablosu - UrunSGKKodId = 58
    print("\n--- SGKKod Tablosu (Id=58) ---")
    try:
        sql = "SELECT * FROM SGKKod WHERE SGKKodId = 58"
        sonuc = db.sorgu_calistir(sql)
        if sonuc:
            for k, v in sonuc[0].items():
                print(f"  {k} = {v}")
    except Exception as e:
        print(f"  Hata: {e}")

    # Urun tablosundaki fiyat hesaplamalari
    print("\n--- Urun Fiyat Bilgileri ---")
    sql = f"""
    SELECT
        u.UrunId,
        u.UrunAdi,
        u.UrunFiyatEtiket as PSF,
        u.UrunFiyatKamu as KamuFiyat,
        u.UrunIskontoKamu,
        u.UrunIskontoYedek,
        u.UrunEsdegerId,
        -- Hesaplamalar
        u.UrunFiyatEtiket - u.UrunFiyatKamu as PSF_Kamu_Fark,
        u.UrunFiyatEtiket * 0.71 * 1.10 as DepocuKDVDahil,
        u.UrunFiyatEtiket * 0.71 * 1.10 * (1 - u.UrunIskontoKamu/100.0) as DepocuIskontolu
    FROM Urun u
    WHERE u.UrunId = {urun_id}
    """
    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        for k, v in sonuc[0].items():
            print(f"  {k} = {v}")

    # Esdeger grubunun referans fiyatini bul
    print("\n--- Esdeger Grubu Referans Fiyat ---")
    sql = f"""
    SELECT
        MIN(u.UrunFiyatKamu) as MinKamuFiyat,
        MAX(u.UrunFiyatKamu) as MaxKamuFiyat,
        AVG(u.UrunFiyatKamu) as OrtKamuFiyat
    FROM Urun u
    WHERE u.UrunEsdegerId = {esdeger_id}
    AND u.UrunSilme = 0
    AND u.UrunFiyatKamu > 0
    """
    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        for k, v in sonuc[0].items():
            print(f"  {k} = {v}")

    # Esdeger grubundaki tum ilaclarin kamu fiyatlari
    print("\n--- Esdeger Grubundaki Ilaclar (Kamu Fiyati) ---")
    sql = f"""
    SELECT TOP 20
        u.UrunId,
        u.UrunAdi,
        u.UrunFiyatKamu,
        u.UrunFiyatEtiket
    FROM Urun u
    WHERE u.UrunEsdegerId = {esdeger_id}
    AND u.UrunSilme = 0
    AND u.UrunFiyatKamu > 0
    ORDER BY u.UrunFiyatKamu
    """
    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        print(f"\n  {'UrunId':<8} {'Kamu':>10} {'PSF':>10} {'Ilac Adi'}")
        print("  " + "-" * 70)
        for row in sonuc:
            print(f"  {row['UrunId']:<8} {float(row['UrunFiyatKamu'] or 0):>10.2f} {float(row['UrunFiyatEtiket'] or 0):>10.2f} {row['UrunAdi'][:40]}")

    # 24.21 hesaplamasi kontrolu
    print("\n--- 24.21 TL HESAPLAMA KONTROLU ---")
    # 143.43 - 119.22 = 24.21 olabilir mi?
    # veya baska bir hesaplama?
    psf = 159.37
    kamu = 143.43
    depocu_kdv_haric = 113.19
    print(f"  PSF: {psf}")
    print(f"  Kamu: {kamu}")
    print(f"  Depocu KDV Haric: {depocu_kdv_haric}")
    print(f"  PSF - Kamu = {psf - kamu:.2f}")
    print(f"  Kamu - Depocu = {kamu - depocu_kdv_haric:.2f}")
    print(f"  PSF * 0.71 = {psf * 0.71:.2f}")
    print(f"  Kamu * 0.71 = {kamu * 0.71:.2f}")

    # 143.43 - 119.22 = 24.21 hesabi
    # 119.22 nereden geliyor?
    print(f"\n  143.43 - 24.21 = {143.43 - 24.21:.2f} (bu deger nedir?)")
    print(f"  159.37 - 24.21 = {159.37 - 24.21:.2f}")
    print(f"  119.22 / 143.43 = {119.22 / 143.43:.4f}")

    db.kapat()

if __name__ == '__main__':
    main()
