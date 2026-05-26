"""
Nöbet Günü Detay Dökümü

Kullanım:
    python tools/nobet_gun_detay.py 2026-03-26
    python tools/nobet_gun_detay.py 2026-03-26 --csv detay.csv

Belirli bir tarih için nöbet shift'inin (gece/pazar/tatil) tüm satışlarını
saat dağılımı ve kalem detayı ile listeler. Botanik EOS'a salt-okunur erişim.
"""

import sys
import os
import csv
from datetime import datetime, date, timedelta
from collections import Counter, defaultdict

# Yukarı klasördeki modüllere erişim
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(SCRIPT_DIR)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python nobet_gun_detay.py <YYYY-MM-DD> [--csv dosya.csv]")
        sys.exit(1)

    try:
        hedef_tarih = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
    except ValueError:
        print(f"Geçersiz tarih: {sys.argv[1]}. Format: YYYY-MM-DD")
        sys.exit(1)

    csv_dosya = None
    if '--csv' in sys.argv:
        idx = sys.argv.index('--csv')
        if idx + 1 < len(sys.argv):
            csv_dosya = sys.argv[idx + 1]

    print(f"\n{'='*70}")
    print(f"NÖBET GÜN DETAYI: {hedef_tarih}")
    print(f"{'='*70}")

    # Bağlantılar
    from botanik_db import get_botanik_db
    from nobet_takvimi import get_nobet_takvimi

    bdb = get_botanik_db()
    if not bdb.baglan():
        print("HATA: Botanik EOS bağlantısı kurulamadı.")
        sys.exit(2)
    nt = get_nobet_takvimi()

    # Satışları çek — geniş aralık (hedef günden 1 gün önce ve 1 gün sonra)
    bas = hedef_tarih - timedelta(days=1)
    bit = hedef_tarih + timedelta(days=1)

    print(f"\nBotanik'ten satışlar çekiliyor: {bas} → {bit}")
    detay = bdb.satis_zaman_detay_getir(
        baslangic_tarih=bas, bitis_tarih=bit, kirilim='tumu'
    )
    print(f"Toplam {len(detay)} satış çekildi.\n")

    # Her satışı nöbet shift'ine göre sınıflandır
    hedef_shift_satislari = []
    for s in detay:
        dt = s.get('tarih')
        if not hasattr(dt, 'hour'):
            continue
        sh = nt.nobet_shift(dt)
        if sh and sh['shift_tarihi'] == hedef_tarih:
            hedef_shift_satislari.append({**s, 'shift_tipi': sh['tip']})

    if not hedef_shift_satislari:
        print(f"⚠ {hedef_tarih} için nöbet shift'inde hiç satış bulunamadı.")
        print(f"  Olası sebep: o gün mesai zamanında satış vardı ama nöbet zamanında yoktu,")
        print(f"  ya da hedef tarih hatalı.")
        return

    # Shift tipi
    tipler = Counter(s['shift_tipi'] for s in hedef_shift_satislari)
    print(f"Shift tipi: {dict(tipler)}")

    # Saat bazlı dağılım
    print(f"\nSAAT BAZLI DAĞILIM:")
    saat_dagi = defaultdict(lambda: {'sayi': 0, 'tl': 0.0, 'kutu': 0.0})
    for s in hedef_shift_satislari:
        h = s['tarih'].hour
        saat_dagi[h]['sayi'] += 1
        saat_dagi[h]['tl'] += float(s.get('tutar') or 0)
        saat_dagi[h]['kutu'] += float(s.get('adet') or 0)

    print(f"  {'Saat':<6} {'Satis':<8} {'Kutu':<8} {'TL':<12}")
    print(f"  {'-'*40}")
    for h in sorted(saat_dagi.keys()):
        d = saat_dagi[h]
        print(f"  {h:02d}:00  {d['sayi']:>6}  {d['kutu']:>6.0f}  {d['tl']:>10,.2f}")

    # Eşik kontrolü
    farkli_saat = len(saat_dagi)
    toplam_satis = sum(d['sayi'] for d in saat_dagi.values())
    toplam_tl = sum(d['tl'] for d in saat_dagi.values())
    toplam_kutu = sum(d['kutu'] for d in saat_dagi.values())

    print(f"\nTOPLAM:")
    print(f"  Satış: {toplam_satis}")
    print(f"  Kutu:  {toplam_kutu:,.0f}")
    print(f"  TL:    {toplam_tl:,.2f}")
    print(f"  Distinct saat: {farkli_saat}")
    print(f"  Onay eşiği: ≥10 satış + ≥4 farklı saat → {'ONAYLI NÖBET' if toplam_satis >= 10 and farkli_saat >= 4 else 'EŞİK ALTI'}")

    # Tüm satışların listesi
    print(f"\nTÜM SATIŞLAR (zamana göre sıralı):")
    print(f"  {'Zaman':<22} {'Kaynak':<10} {'RxId':<10} {'Kutu':<6} {'TL':<12} {'Shift':<8}")
    print(f"  {'-'*70}")
    for s in sorted(hedef_shift_satislari, key=lambda x: x['tarih']):
        zaman = s['tarih'].strftime('%Y-%m-%d %H:%M:%S')
        kaynak = s['kaynak']
        rx_id = s.get('rx_id')
        kutu = s.get('adet', 0)
        tl = s.get('tutar', 0)
        tip = s['shift_tipi']
        print(f"  {zaman}  {kaynak:<10} {rx_id:<10} {kutu:>4.0f}  {tl:>10,.2f}  {tip:<8}")

    # CSV kaydet
    if csv_dosya:
        with open(csv_dosya, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['Zaman', 'Kaynak', 'RxId', 'Kutu', 'TL', 'Shift_Tipi'])
            for s in sorted(hedef_shift_satislari, key=lambda x: x['tarih']):
                w.writerow([
                    s['tarih'].strftime('%Y-%m-%d %H:%M:%S'),
                    s['kaynak'],
                    s.get('rx_id'),
                    s.get('adet', 0),
                    s.get('tutar', 0),
                    s['shift_tipi'],
                ])
        print(f"\nCSV kaydedildi: {csv_dosya}")


if __name__ == "__main__":
    main()
