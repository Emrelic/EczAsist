"""Veritabaninda ilac ara"""
from botanik_db import BotanikDB

db = BotanikDB()
if db.baglan():
    # Amoksisilin/Klavulanik asit kombinasyonu ara
    sql = """
    SELECT TOP 30 u.UrunId, u.UrunAdi,
           COALESCE(u.UrunFiyatEtiket, 0) as PSF,
           (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1) as Stok
    FROM Urun u
    WHERE u.UrunSilme = 0
    AND u.UrunUrunTipId IN (1, 16)
    AND (u.UrunAdi LIKE '%AMOK%' OR u.UrunAdi LIKE '%AUGMENT%' OR u.UrunAdi LIKE '%1000%MG%10%')
    ORDER BY (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1) DESC
    """
    sonuclar = db.sorgu_calistir(sql)
    db.kapat()

    print("Bulunan ilaclar:")
    for s in sonuclar:
        print(f"  {s['UrunAdi']} | Stok: {s['Stok']} | PSF: {s['PSF']}")
else:
    print("Baglanti kurulamadi")
