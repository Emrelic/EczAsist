# -*- coding: utf-8 -*-
"""
Fiyat farki kolonunu bul
"""
import sys
sys.path.insert(0, '.')
from botanik_db import BotanikDB

def main():
    db = BotanikDB()
    if not db.baglan():
        print("Veritabanina baglanilamadi!")
        return

    # Urun tablosundaki tum kolonlari listele - fark ile ilgili
    print("=" * 80)
    print("URUN TABLOSU - FARK ILE ILGILI KOLONLAR")
    print("=" * 80)

    sql_kolonlar = """
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Urun'
    AND (COLUMN_NAME LIKE '%Fark%' OR COLUMN_NAME LIKE '%fark%'
         OR COLUMN_NAME LIKE '%Odenen%' OR COLUMN_NAME LIKE '%odenen%'
         OR COLUMN_NAME LIKE '%Referans%' OR COLUMN_NAME LIKE '%referans%'
         OR COLUMN_NAME LIKE '%SGK%' OR COLUMN_NAME LIKE '%sgk%')
    ORDER BY COLUMN_NAME
    """

    kolonlar = db.sorgu_calistir(sql_kolonlar)
    if kolonlar:
        print("\nBulunan kolonlar:")
        for k in kolonlar:
            print(f"  {k['COLUMN_NAME']:<30} ({k['DATA_TYPE']})")
    else:
        print("Fark ile ilgili kolon bulunamadi")

    # Tum Urun kolonlarini listele
    print("\n" + "=" * 80)
    print("URUN TABLOSU - TUM KOLONLAR")
    print("=" * 80)

    sql_tum = """
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Urun'
    ORDER BY COLUMN_NAME
    """

    tum_kolonlar = db.sorgu_calistir(sql_tum)
    print(f"\nToplam {len(tum_kolonlar)} kolon:")
    for k in tum_kolonlar:
        print(f"  {k['COLUMN_NAME']:<35} ({k['DATA_TYPE']})")

    # AUGMENTIN icin tum verileri getir
    print("\n" + "=" * 80)
    print("AUGMENTIN-BID 1000MG 14 - TUM VERILER")
    print("=" * 80)

    sql_aug = """
    SELECT *
    FROM Urun
    WHERE UrunAdi LIKE '%AUGMENTIN%1000%14%'
    """

    sonuc = db.sorgu_calistir(sql_aug)
    if sonuc:
        ilac = sonuc[0]
        print(f"\nIlac: {ilac.get('UrunAdi', '-')}")
        print("\nTum kolonlar ve degerler:")
        for key, value in sorted(ilac.items()):
            if value is not None and value != '' and value != 0:
                print(f"  {key:<35} = {value}")

    # SGK ile ilgili tablolari ara
    print("\n" + "=" * 80)
    print("SGK / ESDEGER / FARK ILE ILGILI TABLOLAR")
    print("=" * 80)

    sql_tablolar = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
    AND (TABLE_NAME LIKE '%SGK%' OR TABLE_NAME LIKE '%Esdeger%'
         OR TABLE_NAME LIKE '%Fark%' OR TABLE_NAME LIKE '%Referans%'
         OR TABLE_NAME LIKE '%Kamu%' OR TABLE_NAME LIKE '%Fiyat%')
    ORDER BY TABLE_NAME
    """

    tablolar = db.sorgu_calistir(sql_tablolar)
    if tablolar:
        print("\nBulunan tablolar:")
        for t in tablolar:
            print(f"  {t['TABLE_NAME']}")

    # UrunSGKKodId = 58 icin SGK tablosuna bak
    print("\n" + "=" * 80)
    print("SGKKod TABLOSU KONTROLU")
    print("=" * 80)

    # Tablonun var olup olmadigini kontrol et
    sql_sgk_kontrol = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%SGK%'
    """
    sgk_tablolar = db.sorgu_calistir(sql_sgk_kontrol)
    if sgk_tablolar:
        for t in sgk_tablolar:
            tablo_adi = t['TABLE_NAME']
            print(f"\n--- {tablo_adi} kolonlari ---")
            sql_kol = f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{tablo_adi}'
            ORDER BY COLUMN_NAME
            """
            kolonlar = db.sorgu_calistir(sql_kol)
            for k in kolonlar:
                print(f"  {k['COLUMN_NAME']:<30} ({k['DATA_TYPE']})")

    # Esdeger tablosuna bak
    print("\n" + "=" * 80)
    print("ESDEGER TABLOSU (EsdegerId=105)")
    print("=" * 80)

    sql_esdeger_tablo = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%Esdeger%'
    """
    esdeger_tablolar = db.sorgu_calistir(sql_esdeger_tablo)
    if esdeger_tablolar:
        for t in esdeger_tablolar:
            tablo_adi = t['TABLE_NAME']
            print(f"\n--- {tablo_adi} ---")

            # Kolonlari goster
            sql_kol = f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{tablo_adi}'
            ORDER BY COLUMN_NAME
            """
            kolonlar = db.sorgu_calistir(sql_kol)
            for k in kolonlar:
                print(f"  {k['COLUMN_NAME']:<30} ({k['DATA_TYPE']})")

            # EsdegerId=105 verisi
            try:
                sql_veri = f"SELECT TOP 1 * FROM {tablo_adi} WHERE EsdegerId = 105 OR Id = 105"
                veri = db.sorgu_calistir(sql_veri)
                if veri:
                    print(f"\n  EsdegerId=105 verisi:")
                    for key, val in veri[0].items():
                        if val is not None:
                            print(f"    {key} = {val}")
            except:
                pass

    db.kapat()

if __name__ == '__main__':
    main()
