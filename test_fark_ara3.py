# -*- coding: utf-8 -*-
"""
Fiyat Farki kolonunu tum tablolarda ara
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
    print("TUM TABLOLARDA FARK/REFERANS KOLONU ARA")
    print("=" * 80)

    # Tum kolonlarda Fark, Referans, Odenen arama
    sql = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE COLUMN_NAME LIKE '%Fark%'
       OR COLUMN_NAME LIKE '%Referans%'
       OR COLUMN_NAME LIKE '%Odenen%'
       OR COLUMN_NAME LIKE '%odenen%'
       OR COLUMN_NAME LIKE '%SGKOdeme%'
       OR COLUMN_NAME LIKE '%KamuOdeme%'
    ORDER BY TABLE_NAME, COLUMN_NAME
    """

    kolonlar = db.sorgu_calistir(sql)
    print(f"\nBulunan {len(kolonlar)} kolon:")
    for k in kolonlar:
        print(f"  {k['TABLE_NAME']}.{k['COLUMN_NAME']} ({k['DATA_TYPE']})")

    # ReceteIlaclari tablosuna bak - fiyat farki orada olabilir
    print("\n" + "=" * 80)
    print("ReceteIlaclari TABLOSU KOLONLARI")
    print("=" * 80)

    sql = """
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ReceteIlaclari'
    ORDER BY COLUMN_NAME
    """

    kolonlar = db.sorgu_calistir(sql)
    for k in kolonlar:
        print(f"  {k['COLUMN_NAME']:<30} ({k['DATA_TYPE']})")

    # AUGMENTIN 1000MG 14 icin son recete kaydina bak
    print("\n" + "=" * 80)
    print("AUGMENTIN 1000MG 14 - SON RECETE KAYDI")
    print("=" * 80)

    sql = """
    SELECT TOP 1 ri.*, ra.RxReceteTarihi
    FROM ReceteIlaclari ri
    JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
    WHERE ri.RIUrunId = 2766
    AND ra.RxSilme = 0
    ORDER BY ra.RxReceteTarihi DESC
    """

    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        print("\nSon recete kaydi:")
        for k, v in sonuc[0].items():
            if v is not None and v != 0:
                print(f"  {k:<30} = {v}")

    # ReceteHesap tablosuna bak
    print("\n" + "=" * 80)
    print("ReceteHesap TABLOSU")
    print("=" * 80)

    sql = """
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ReceteHesap'
    ORDER BY COLUMN_NAME
    """

    kolonlar = db.sorgu_calistir(sql)
    if kolonlar:
        for k in kolonlar:
            print(f"  {k['COLUMN_NAME']:<30} ({k['DATA_TYPE']})")

    # 119.22 degerini tum tablolarda ara
    print("\n" + "=" * 80)
    print("119.22 DEGERINI ARA (Referans Fiyat olabilir)")
    print("=" * 80)

    # Urun tablosunda 119.22 ara
    sql = """
    SELECT UrunId, UrunAdi, UrunFiyatKamu, UrunFiyatEtiket
    FROM Urun
    WHERE UrunFiyatKamu BETWEEN 119.20 AND 119.25
    OR UrunFiyatEtiket BETWEEN 119.20 AND 119.25
    """
    sonuc = db.sorgu_calistir(sql)
    if sonuc:
        print("\nUrun tablosunda 119.22 civarinda:")
        for row in sonuc:
            print(f"  {row['UrunId']}: {row['UrunAdi'][:40]} - Kamu: {row['UrunFiyatKamu']}, PSF: {row['UrunFiyatEtiket']}")

    db.kapat()

if __name__ == '__main__':
    main()
