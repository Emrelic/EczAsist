"""
BotanikDB sinifi calede ile sorunsuz calisiyor mu? Smoke test.
- Hicbir yazma denemesi yapmaz.
- Sadece okuma sorgusu (sys.tables) ve bir hasta sayisi.
"""
import sys
sys.path.insert(0, r"C:\Users\ana\OneDrive\Desktop\Uibul3.0\EczAsist")

from botanik_db import BotanikDB

def main():
    print("=" * 60)
    print("BotanikDB + calede smoke test")
    print("=" * 60)

    db = BotanikDB()
    print(f"[INFO] Kullanilan kullanici: {db.config.get('user')}")

    if not db.baglan():
        print("[FAIL] BotanikDB.baglan() basarisiz")
        sys.exit(1)
    print("[OK] BotanikDB.baglan() basarili")

    # Sorgu 1: kac tablo var?
    r = db.sorgu_calistir("SELECT COUNT(*) AS tablo_sayisi FROM sys.tables")
    if r:
        print(f"[OK] sys.tables COUNT -> {r[0]['tablo_sayisi']}")
    else:
        print(f"[FAIL] sorgu_calistir hata: {db.son_sorgu_hatasi}")

    # Sorgu 2: ilk 5 tablo adi
    r = db.sorgu_calistir("SELECT TOP 5 name FROM sys.tables ORDER BY name")
    if r:
        print(f"[OK] Ilk 5 tablo: {[row['name'] for row in r]}")
    else:
        print(f"[FAIL] sorgu_calistir hata: {db.son_sorgu_hatasi}")

    # Sorgu 3: hasta tablosu varsa kac kayit (Eczane DB'sinde olabilecek genel adlar)
    for tablo_adi in ['Hasta', 'Hastalar', 'Recete', 'Receteler']:
        sorgu = f"SELECT COUNT(*) AS sayi FROM {tablo_adi}"
        r = db.sorgu_calistir(sorgu)
        if r:
            print(f"[OK] {tablo_adi} kayit sayisi: {r[0]['sayi']}")
            break
        else:
            # Hata kayit yok degil, tablo yok demektir — sessizce gec
            pass

    db.kapat()
    print("=" * 60)
    print("Smoke test tamam.")

if __name__ == "__main__":
    main()
