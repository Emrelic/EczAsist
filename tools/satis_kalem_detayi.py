"""
Satış Kalem Detayı Dökümü

Bir datetime aralığında her satışı KALEM bazında (hasta, doktor, kurum, ürün,
adet, fiyat) listeler.

Kullanım:
    python tools/satis_kalem_detayi.py "2026-03-27 05:00:00" "2026-03-27 09:00:00"
    python tools/satis_kalem_detayi.py "2026-03-27 05:00:00" "2026-03-27 09:00:00" --csv detay.csv
"""

import sys
import os
import csv
from datetime import datetime
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(SCRIPT_DIR)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)


def main():
    if len(sys.argv) < 3:
        print("Kullanım: python satis_kalem_detayi.py 'YYYY-MM-DD HH:MM:SS' 'YYYY-MM-DD HH:MM:SS' [--csv dosya.csv]")
        sys.exit(1)

    try:
        bas = datetime.strptime(sys.argv[1], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            bas = datetime.strptime(sys.argv[1], '%Y-%m-%d %H:%M')
        except ValueError:
            print(f"Geçersiz başlangıç: {sys.argv[1]}")
            sys.exit(1)
    try:
        bit = datetime.strptime(sys.argv[2], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            bit = datetime.strptime(sys.argv[2], '%Y-%m-%d %H:%M')
        except ValueError:
            print(f"Geçersiz bitiş: {sys.argv[2]}")
            sys.exit(1)

    csv_dosya = None
    if '--csv' in sys.argv:
        i = sys.argv.index('--csv')
        if i + 1 < len(sys.argv):
            csv_dosya = sys.argv[i + 1]

    print(f"\n{'='*90}")
    print(f"SATIŞ KALEM DETAYI: {bas} → {bit}")
    print(f"{'='*90}")

    from botanik_db import get_botanik_db
    bdb = get_botanik_db()
    if not bdb.baglan():
        print("HATA: Botanik EOS bağlantısı kurulamadı.")
        sys.exit(2)

    kalemler = bdb.satis_kalem_detayi_getir(bas, bit, kirilim='tumu')
    print(f"\nToplam {len(kalemler)} kalem çekildi.\n")
    if not kalemler:
        print("Bu aralıkta satış kalemi yok.")
        return

    # RxId bazlı gruplama (her reçete/elden için kalemleri grupla)
    rx_grup = defaultdict(list)
    for k in kalemler:
        anahtar = (k['Kaynak'], k['RxId'])
        rx_grup[anahtar].append(k)

    # Sıralı liste
    sirali = sorted(rx_grup.keys(),
                    key=lambda key: rx_grup[key][0]['IslemTarihi'])

    # Reçete bazlı yazdır
    print("-" * 90)
    for kaynak, rx_id in sirali:
        kalem_listesi = rx_grup[(kaynak, rx_id)]
        ilk = kalem_listesi[0]
        zaman = ilk['IslemTarihi']
        zaman_str = zaman.strftime('%Y-%m-%d %H:%M:%S') if hasattr(zaman, 'strftime') else str(zaman)

        hasta = ilk['HastaAdi'] or '-'
        doktor = ilk['DoktorAdi'] or '-'
        kurum = ilk['KurumAdi'] or '-'
        tesis = ilk['TesisAdi'] or '-'

        toplam_tutar = sum(k['Tutar'] for k in kalem_listesi)
        toplam_adet = sum(k['Adet'] for k in kalem_listesi)

        print(f"\n[{kaynak}] RxId={rx_id}  Zaman: {zaman_str}")
        print(f"  Hasta:  {hasta}")
        if kaynak == 'RECETE':
            print(f"  Doktor: {doktor}")
            print(f"  Kurum:  {kurum}    Tesis: {tesis}")
        print(f"  Toplam: {len(kalem_listesi)} kalem, {toplam_adet:.0f} kutu, {toplam_tutar:,.2f} TL")
        print(f"  Kalemler:")
        for k in kalem_listesi:
            print(f"    - {k['UrunAdi'][:60]:60}  adet={k['Adet']:.0f}  birim={k['BirimFiyat']:.2f}  toplam={k['Tutar']:,.2f}")

    print("\n" + "=" * 90)
    print(f"GENEL TOPLAM: {len(rx_grup)} satış / {len(kalemler)} kalem")
    toplam_tutar = sum(k['Tutar'] for k in kalemler)
    toplam_adet = sum(k['Adet'] for k in kalemler)
    print(f"  Toplam adet:  {toplam_adet:,.0f}")
    print(f"  Toplam tutar: {toplam_tutar:,.2f} TL")
    recete_say = sum(1 for k in rx_grup if k[0] == 'RECETE')
    elden_say = sum(1 for k in rx_grup if k[0] == 'ELDEN')
    print(f"  Reçeteli: {recete_say} satış / Elden: {elden_say} satış")

    if csv_dosya:
        with open(csv_dosya, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['Zaman', 'Kaynak', 'RxId', 'Hasta', 'Doktor', 'Kurum',
                        'Tesis', 'Urun', 'Adet', 'BirimFiyat', 'Tutar'])
            for k in kalemler:
                w.writerow([
                    k['IslemTarihi'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(k['IslemTarihi'], 'strftime') else k['IslemTarihi'],
                    k['Kaynak'], k['RxId'], k['HastaAdi'], k['DoktorAdi'],
                    k['KurumAdi'], k['TesisAdi'], k['UrunAdi'],
                    k['Adet'], k['BirimFiyat'], k['Tutar'],
                ])
        print(f"\nCSV kaydedildi: {csv_dosya}")


if __name__ == "__main__":
    main()
