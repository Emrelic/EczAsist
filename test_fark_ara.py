# -*- coding: utf-8 -*-
"""
24.21 TL fark degerini veritabaninda ara
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
    print("24.21 TL DEGERINI VERITABANINDA ARA")
    print("=" * 80)

    # Tum tablolari al
    sql_tablolar = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
    ORDER BY TABLE_NAME
    """

    tablolar = db.sorgu_calistir(sql_tablolar)

    # Her tabloda 24.21 degerini ara
    print("\n24.21 veya 24.20-24.22 araliginda deger araniyor...\n")

    for tablo in tablolar:
        tablo_adi = tablo['TABLE_NAME']

        # Tablonun numeric kolonlarini bul
        sql_kolonlar = f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{tablo_adi}'
        AND DATA_TYPE IN ('numeric', 'decimal', 'float', 'money', 'real')
        """

        kolonlar = db.sorgu_calistir(sql_kolonlar)
        if not kolonlar:
            continue

        for kolon in kolonlar:
            kolon_adi = kolon['COLUMN_NAME']
            try:
                # Augmentin ile iliskili olabilecek kayitlarda 24.21 ara
                sql_ara = f"""
                SELECT TOP 5 *
                FROM {tablo_adi}
                WHERE {kolon_adi} BETWEEN 24.20 AND 24.22
                """
                sonuc = db.sorgu_calistir(sql_ara)
                if sonuc:
                    print(f"BULUNDU: {tablo_adi}.{kolon_adi}")
                    for row in sonuc:
                        print(f"  Deger: {row.get(kolon_adi)}")
                        # Ilk 5 kolonu goster
                        for i, (k, v) in enumerate(row.items()):
                            if i < 8 and v is not None:
                                print(f"    {k} = {v}")
                        print()
            except Exception as e:
                pass  # Hata varsa atla

    # Ayrica Urun tablosunda AUGMENTIN ile iliskili tum fiyat/numeric alanlari kontrol et
    print("\n" + "=" * 80)
    print("AUGMENTIN 1000MG 14 - TUM NUMERIC DEGERLER")
    print("=" * 80)

    sql_aug = """
    SELECT *
    FROM Urun u
    WHERE u.UrunAdi LIKE '%AUGMENTIN%1000%14%'
    """
    sonuc = db.sorgu_calistir(sql_aug)
    if sonuc:
        ilac = sonuc[0]
        urun_id = ilac.get('UrunId')
        print(f"\nUrunId: {urun_id}")
        print(f"UrunAdi: {ilac.get('UrunAdi')}")

        # Tum numeric degerleri goster
        for key, value in sorted(ilac.items()):
            if value is not None and isinstance(value, (int, float)) and value != 0:
                print(f"  {key:<30} = {value}")

        # EsdegerId ile iliskili tablolara bak
        esdeger_id = ilac.get('UrunEsdegerId')
        print(f"\n--- EsdegerId = {esdeger_id} ile iliskili veriler ---")

        # EsdegerListesi tablosunu kontrol et
        try:
            sql_esd = f"SELECT * FROM EsdegerListesi WHERE EsdegerId = {esdeger_id}"
            esd_sonuc = db.sorgu_calistir(sql_esd)
            if esd_sonuc:
                print("\nEsdegerListesi:")
                for k, v in esd_sonuc[0].items():
                    if v is not None:
                        print(f"  {k} = {v}")
        except:
            pass

    db.kapat()

if __name__ == '__main__':
    main()
