# -*- coding: utf-8 -*-
"""
AUGMENTIN icin RIFiyatFarki ve RHFiyatFarki degerlerini bul
"""
import sys
sys.path.insert(0, '.')
from botanik_db import BotanikDB

def main():
    db = BotanikDB()
    if not db.baglan():
        print("Veritabanina baglanilamadi!")
        return

    print("=" * 80)
    print("AUGMENTIN 1000MG 14 - FIYAT FARKI KAYITLARI")
    print("=" * 80)

    # RIFiyatFarki > 0 olan AUGMENTIN kayitlari
    print("\n--- ReceteIlaclari - RIFiyatFarki > 0 olan kayitlar ---")
    sql = """
    SELECT TOP 10
        ri.RIId,
        ri.RIRxId,
        ri.RIUrunId,
        ri.RIEtiketFiyati,
        ri.RIKurumFiyati,
        ri.RIFiyatFarki,
        ri.RIAdet,
        ra.RxReceteTarihi
    FROM ReceteIlaclari ri
    JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
    WHERE ri.RIUrunId = 2766
    AND ri.RIFiyatFarki > 0
    AND ra.RxSilme = 0
    ORDER BY ra.RxReceteTarihi DESC
    """

    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        for row in sonuc:
            print(f"\n  RxId: {row['RIRxId']}, Tarih: {row['RxReceteTarihi']}")
            print(f"    Etiket: {row['RIEtiketFiyati']}, Kurum: {row['RIKurumFiyati']}, FiyatFarki: {row['RIFiyatFarki']}")
    else:
        print("  FiyatFarki > 0 olan kayit bulunamadi")

    # ReceteHesap tablosunda FiyatFarki
    print("\n--- ReceteHesap - RHFiyatFarki > 0 olan AUGMENTIN receteleri ---")
    sql = """
    SELECT TOP 10
        rh.RHRxId,
        rh.RHFiyatFarki,
        rh.RHEtiketToplam,
        rh.RHKurumOdemesi,
        rh.RHHastaReceteOdemesi,
        ra.RxReceteTarihi
    FROM ReceteHesap rh
    JOIN ReceteAna ra ON rh.RHRxId = ra.RxId
    WHERE ra.RxId IN (
        SELECT DISTINCT ri.RIRxId
        FROM ReceteIlaclari ri
        WHERE ri.RIUrunId = 2766
    )
    AND rh.RHFiyatFarki > 0
    ORDER BY ra.RxReceteTarihi DESC
    """

    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        for row in sonuc:
            print(f"\n  RxId: {row['RHRxId']}, Tarih: {row['RxReceteTarihi']}")
            print(f"    FiyatFarki: {row['RHFiyatFarki']}, Etiket: {row['RHEtiketToplam']}, Kurum: {row['RHKurumOdemesi']}, Hasta: {row['RHHastaReceteOdemesi']}")
    else:
        print("  FiyatFarki > 0 olan hesap kaydi bulunamadi")

    # 24.21 yakin degerleri ReceteIlaclari.RIFiyatFarki'da ara
    print("\n--- 24.21 civari FiyatFarki degerleri ---")
    sql = """
    SELECT TOP 10
        ri.RIUrunId,
        u.UrunAdi,
        ri.RIFiyatFarki,
        ri.RIEtiketFiyati,
        ri.RIKurumFiyati,
        ra.RxReceteTarihi
    FROM ReceteIlaclari ri
    JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
    JOIN Urun u ON ri.RIUrunId = u.UrunId
    WHERE ri.RIFiyatFarki BETWEEN 24.00 AND 24.50
    ORDER BY ra.RxReceteTarihi DESC
    """

    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        for row in sonuc:
            print(f"\n  {row['UrunAdi'][:50]}")
            print(f"    FiyatFarki: {row['RIFiyatFarki']}, Etiket: {row['RIEtiketFiyati']}, Kurum: {row['RIKurumFiyati']}")
    else:
        print("  24.21 civari fiyat farki bulunamadi")

    # Esdeger grup icindeki ilaclar icin RIFiyatFarki kontrolu
    print("\n--- EsdegerId=105 grubundaki ilaclar icin FiyatFarki ---")
    sql = """
    SELECT
        u.UrunId,
        u.UrunAdi,
        MAX(ri.RIFiyatFarki) as MaxFark,
        AVG(ri.RIFiyatFarki) as OrtFark,
        COUNT(*) as KayitSayisi
    FROM ReceteIlaclari ri
    JOIN Urun u ON ri.RIUrunId = u.UrunId
    WHERE u.UrunEsdegerId = 105
    AND ri.RIFiyatFarki > 0
    GROUP BY u.UrunId, u.UrunAdi
    ORDER BY MaxFark DESC
    """

    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        print(f"\n  {'Ilac':<45} {'MaxFark':>10} {'OrtFark':>10} {'Kayit':>8}")
        print("  " + "-" * 75)
        for row in sonuc:
            print(f"  {row['UrunAdi'][:44]:<45} {float(row['MaxFark'] or 0):>10.2f} {float(row['OrtFark'] or 0):>10.2f} {row['KayitSayisi']:>8}")
    else:
        print("  FiyatFarki > 0 olan kayit bulunamadi")

    db.kapat()

if __name__ == '__main__':
    main()
