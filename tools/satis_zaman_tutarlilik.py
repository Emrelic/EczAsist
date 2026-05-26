"""
Satış Zaman Tutarlılık Kontrolü

Bir tarihte/aralıkta yapılan satışların zaman damgalarının doğruluğunu test eder.
4 olası anomaliyi tespit eder:
  1. Saat dilimi sapması (RxIslemTarihi vs RxKayitTarihi farkı sabit ~3sa veya benzeri)
  2. Toplu/geç kayıt (RxKayitTarihi >> RxIslemTarihi)
  3. Sistem saati bozulması (RxIslemTarihi anormal, kayıt zamanı doğru)
  4. Gerçek erken nöbet (her iki zaman da tutarlı)

Kullanım:
    python tools/satis_zaman_tutarlilik.py 2026-03-27
    python tools/satis_zaman_tutarlilik.py 2026-03-27 --saat 5 9   # Sadece 05:00-09:00 aralığı
    python tools/satis_zaman_tutarlilik.py 2026-03-27 --kiyas 14   # 14 gün önce/sonra ile kıyas
"""

import sys
import os
from datetime import datetime, date, timedelta
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(SCRIPT_DIR)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python satis_zaman_tutarlilik.py YYYY-MM-DD [--saat BAS BIT] [--kiyas N]")
        sys.exit(1)

    try:
        hedef = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
    except ValueError:
        print(f"Geçersiz tarih: {sys.argv[1]}")
        sys.exit(1)

    saat_bas, saat_bit = 0, 23
    if '--saat' in sys.argv:
        i = sys.argv.index('--saat')
        saat_bas = int(sys.argv[i + 1])
        saat_bit = int(sys.argv[i + 2])

    kiyas_gun = 14
    if '--kiyas' in sys.argv:
        i = sys.argv.index('--kiyas')
        kiyas_gun = int(sys.argv[i + 1])

    print(f"\n{'='*80}")
    print(f"SATIŞ ZAMAN TUTARLILIK KONTROLÜ")
    print(f"Hedef tarih: {hedef}, saat aralığı: {saat_bas:02d}:00–{saat_bit:02d}:59")
    print(f"Anomali kıyas: ±{kiyas_gun} gün")
    print(f"{'='*80}")

    from botanik_db import get_botanik_db
    bdb = get_botanik_db()
    if not bdb.baglan():
        print("HATA: Botanik EOS bağlantısı kurulamadı.")
        sys.exit(2)

    # ------------------------------------------------------------------
    # 1) Hedef saat aralığındaki kayıtlar — RxIslemTarihi vs RxKayitTarihi
    # ------------------------------------------------------------------
    bas_dt = datetime.combine(hedef, datetime.min.time()).replace(hour=saat_bas)
    bit_dt = datetime.combine(hedef, datetime.min.time()).replace(hour=saat_bit, minute=59, second=59)

    print(f"\n--- 1. ZAMAN DAMGASI KARŞILAŞTIRMA ({bas_dt} → {bit_dt}) ---\n")
    kayitlar = bdb.satis_zaman_tutarlilik_getir(bas_dt, bit_dt)
    print(f"Toplam {len(kayitlar)} satış bu aralıkta.\n")

    if not kayitlar:
        print("Bu aralıkta satış yok — kontrol için tarih/saat değiştir.")
        return

    print(f"{'#':<4} {'Kaynak':<8} {'RxId':<10} {'IslemTarihi':<22} {'KayitTarihi':<22} {'Fark':<14}")
    print("-" * 80)
    fark_degerleri = []
    fark_negatif = 0
    fark_buyuk = 0  # > 10 dakika
    fark_sabit_aralikta = defaultdict(int)  # ~saat olarak sınıfla
    for i, k in enumerate(kayitlar, 1):
        islem = k['IslemTarihi']
        kayit = k['KayitTarihi']
        fark = k['FarkSn']
        islem_s = islem.strftime('%Y-%m-%d %H:%M:%S') if hasattr(islem, 'strftime') else str(islem)
        kayit_s = kayit.strftime('%Y-%m-%d %H:%M:%S') if hasattr(kayit, 'strftime') else str(kayit)
        if fark is None:
            fark_str = "?"
        else:
            fark_degerleri.append(fark)
            if fark < 0:
                fark_negatif += 1
                fark_str = f"{fark}sn ⚠NEGATİF"
            elif fark > 600:
                fark_buyuk += 1
                if fark > 3600:
                    fark_str = f"{fark//3600}sa {(fark%3600)//60}dk"
                else:
                    fark_str = f"{fark//60}dk {fark%60}sn"
            else:
                fark_str = f"{fark}sn"
            # Fark sabit ~saat olarak sınıflandır
            saat_fark = round(fark / 3600.0, 1)
            fark_sabit_aralikta[saat_fark] += 1
        print(f"{i:<4} {k['Kaynak']:<8} {k['RxId']:<10} {islem_s:<22} {kayit_s:<22} {fark_str:<14}")

    # ------------------------------------------------------------------
    # 2) ANALİZ — anomali sinyalleri
    # ------------------------------------------------------------------
    print(f"\n--- 2. ANOMALİ SİNYAL ANALİZİ ---\n")

    if fark_degerleri:
        ort_fark = sum(fark_degerleri) / len(fark_degerleri)
        med_fark = sorted(fark_degerleri)[len(fark_degerleri) // 2]
        min_fark = min(fark_degerleri)
        max_fark = max(fark_degerleri)
        print(f"İşlem ↔ Kayıt fark istatistikleri:")
        print(f"  Ortalama: {ort_fark:.0f}sn ({ort_fark/60:.1f}dk)")
        print(f"  Medyan:   {med_fark}sn")
        print(f"  Min:      {min_fark}sn  Max: {max_fark}sn")
        print(f"  Negatif fark sayısı: {fark_negatif}")
        print(f"  >10dk fark sayısı:   {fark_buyuk}")

        print(f"\nSabit fark dağılımı (~saat):")
        for saat_f, count in sorted(fark_sabit_aralikta.items()):
            yuzde = (count / len(kayitlar)) * 100
            print(f"  {saat_f:>+6.1f} sa : {count} kayıt ({yuzde:.0f}%)")

        # Sinyal yorumu
        print(f"\nSinyal yorumu:")
        if fark_negatif > len(kayitlar) * 0.3:
            print("  ⚠ Negatif fark çok yüksek → KAYIT işlem zamanından ÖNCE → sistem saati bozulmuş")
        if abs(ort_fark) > 3 * 3600 and len(set(fark_sabit_aralikta.keys())) <= 2:
            print(f"  ⚠ Sabit büyük fark (~{ort_fark/3600:.1f}sa) → SAAT DİLİMİ SAPMASI olası")
        if max_fark > 24 * 3600 and med_fark < 600:
            print(f"  ⚠ Bazı kayıtlar çok geç girilmiş (max {max_fark/3600:.0f}sa) → TOPLU/GEÇ KAYIT olası")
        if -10 <= ort_fark <= 60 and fark_negatif == 0 and fark_buyuk == 0:
            print(f"  ✓ Zaman damgaları tutarlı (kayıt anında yapıldı) → GERÇEK SATIŞ olası")

    # ------------------------------------------------------------------
    # 3) RxId ardışıklık analizi (toplu insert mi?)
    # ------------------------------------------------------------------
    print(f"\n--- 3. RxId ARDIŞIKLIK (toplu insert tespiti) ---\n")
    recete_idler = sorted([k['RxId'] for k in kayitlar if k['Kaynak'] == 'RECETE'])
    elden_idler = sorted([k['RxId'] for k in kayitlar if k['Kaynak'] == 'ELDEN'])

    for ad, ids in [('Reçete', recete_idler), ('Elden', elden_idler)]:
        if not ids:
            continue
        print(f"\n{ad} RxId'leri:")
        print(f"  Min: {ids[0]}, Max: {ids[-1]}, Aralık: {ids[-1]-ids[0]} (kayıt sayısı: {len(ids)})")
        if len(ids) > 1:
            ardisik = sum(1 for i in range(1, len(ids)) if ids[i] - ids[i-1] == 1)
            yuzde = (ardisik / (len(ids) - 1)) * 100
            print(f"  Ardışık (Δ=1) çift sayısı: {ardisik}/{len(ids)-1} ({yuzde:.0f}%)")
            if yuzde > 80:
                print(f"  ⚠ Çok ardışık → toplu kayıt veya hızlı arka arkaya işlem")
            elif yuzde > 50:
                print(f"  → Genel olarak ardışık ama bazı boşluklar var (normal)")
            else:
                print(f"  → ID'ler dağılmış → diğer reçeteler arasına serpişmiş (normal trafik)")

    # ------------------------------------------------------------------
    # 4) KIYAS — geçmiş günler aynı saatler
    # ------------------------------------------------------------------
    print(f"\n--- 4. KIYAS: Aynı saatler {kiyas_gun} gün önce + sonra ---\n")
    kiyas_bas = hedef - timedelta(days=kiyas_gun)
    kiyas_bit = hedef + timedelta(days=kiyas_gun)
    kiyas = bdb.gun_saat_yogunlugu_getir(kiyas_bas, kiyas_bit)
    # Saat aralığındaki günlük satış sayısı
    gun_saat = defaultdict(lambda: defaultdict(int))
    for r in kiyas:
        gun_saat[r['Tarih']][r['Saat']] = r['SatisSayisi']

    print(f"{'Tarih':<12} ", end='')
    for h in range(saat_bas, saat_bit + 1):
        print(f"{h:02d}".rjust(4), end='')
    print(f"  | Top.")
    print("-" * (14 + 4 * (saat_bit - saat_bas + 1) + 8))

    hedef_topla = 0
    for d in sorted(gun_saat.keys()):
        if not (kiyas_bas <= d <= kiyas_bit):
            continue
        prefix = '>' if d == hedef else ' '
        print(f"{prefix} {d}  ", end='')
        gun_top = 0
        for h in range(saat_bas, saat_bit + 1):
            sayi = gun_saat[d].get(h, 0)
            gun_top += sayi
            if sayi == 0:
                print(f"{'·':>4}", end='')
            else:
                # Yüksek vurgu (15+ kayıt anomali)
                marker = '*' if sayi >= 15 else ''
                print(f"{sayi:>4}", end='')
        print(f"  | {gun_top}{'*' if d == hedef else ''}")
        if d == hedef:
            hedef_topla = gun_top

    print(f"\nYorum:")
    digerleri = [sum(gun_saat[d].get(h, 0) for h in range(saat_bas, saat_bit + 1))
                  for d in gun_saat if d != hedef]
    if digerleri:
        ort_diger = sum(digerleri) / len(digerleri)
        print(f"  Hedef gün ({hedef}) toplam: {hedef_topla}")
        print(f"  Diğer günlerin ortalaması: {ort_diger:.1f}")
        if hedef_topla > ort_diger * 5 and ort_diger < 3:
            print(f"  ⚠ Hedef gün diğer günlere göre ÇOK YÜKSEK → muhtemelen TOPLU KAYIT")
        elif ort_diger > 0 and 0.5 <= hedef_topla / ort_diger <= 2.0:
            print(f"  ✓ Hedef gün diğer günlerle BENZER → normal eczane trafiği (tekrarlanan kalıp)")
        elif hedef_topla > 0 and ort_diger < 0.5:
            print(f"  → Hedef gün anormal yoğun, diğerleri boş → o gün özel (nöbet?)")

    print(f"\n{'='*80}")
    print("Yorum kılavuzu:")
    print(f"  • Fark ~3 saat sabit ve tüm kayıtlarda aynı → SAAT DİLİMİ SAPMASI (UTC vs TR)")
    print(f"  • Fark çok büyük + RxId çok ardışık → TOPLU GİRİŞ (geçmiş reçeteler sonra girilmiş)")
    print(f"  • Fark <1 dakika + RxId dağılmış → GERÇEK SATIŞ (kayıt anında yapılmış)")
    print(f"  • Kıyas günlerde aynı saatte satış yok ama hedef günde var → NÖBET veya ANOMALİ")


if __name__ == "__main__":
    main()
