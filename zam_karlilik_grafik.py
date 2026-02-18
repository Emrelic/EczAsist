"""
Zam Karlılık Grafiği - Sipariş Optimizasyonu Görselleştirme
Belirli ilaçlar için zam öncesi optimum alım miktarını ve karlılık eğrisini gösterir
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import numpy as np
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import sys

# Türkçe karakter desteği
plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'sans-serif']


def veritabanindan_ilac_bilgisi_al(ilac_adi_parcasi: str):
    """Veritabanından ilaç bilgilerini çek"""
    try:
        from botanik_db import BotanikDB
        db = BotanikDB()
        if not db.baglan():
            print(f"Veritabanı bağlantısı kurulamadı!")
            return None

        # Son 6 ayın satış verilerini al
        bugun = datetime.now()
        baslangic = (bugun - relativedelta(months=6)).strftime('%Y-%m-%d')

        sql = f"""
        ;WITH CikisVerileri AS (
            -- SGK satışları
            SELECT ri.RIUrunId as UrunId, ri.RIAdet as Adet
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            AND ra.RxKayitTarihi >= '{baslangic}'

            UNION ALL

            -- Elden satışları
            SELECT ei.RIUrunId as UrunId, ei.RIAdet as Adet
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            AND ea.RxKayitTarihi >= '{baslangic}'
        )
        SELECT TOP 1
            u.UrunId,
            u.UrunAdi,
            COALESCE(u.UrunFiyatEtiket, 0) as PSF,
            COALESCE(u.UrunIskontoKamu, 0) as IskontoKamu,
            CASE
                WHEN u.UrunUrunTipId IN (1, 16) THEN
                    (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1)
                ELSE
                    (COALESCE(u.UrunStokDepo,0) + COALESCE(u.UrunStokRaf,0) + COALESCE(u.UrunStokAcik,0))
            END as Stok,
            COALESCE((SELECT SUM(Adet) FROM CikisVerileri WHERE UrunId = u.UrunId), 0) as ToplamCikis
        FROM Urun u
        JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        WHERE u.UrunSilme = 0
        AND u.UrunAdi LIKE '%{ilac_adi_parcasi}%'
        AND ut.UrunTipAdi IN ('İLAÇ', 'PASİF İLAÇ')
        ORDER BY
            CASE WHEN u.UrunAdi LIKE '{ilac_adi_parcasi}%' THEN 0 ELSE 1 END,
            (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1) DESC
        """

        sonuclar = db.sorgu_calistir(sql)
        db.kapat()

        if sonuclar:
            veri = sonuclar[0]
            # Depocu fiyat hesapla
            psf = float(veri.get('PSF', 0) or 0)
            iskonto = float(veri.get('IskontoKamu', 0) or 0)
            depocu_fiyat = psf * 0.71 * 1.10 * (1 - iskonto / 100) if psf > 0 else 0

            toplam_cikis = float(veri.get('ToplamCikis', 0) or 0)
            aylik_ort = toplam_cikis / 6  # 6 aylık ortalama

            return {
                'UrunId': veri.get('UrunId'),
                'UrunAdi': veri.get('UrunAdi'),
                'PSF': psf,
                'IskontoKamu': iskonto,
                'DepocuFiyat': depocu_fiyat,
                'Stok': int(veri.get('Stok', 0) or 0),
                'AylikOrt': aylik_ort,
                'ToplamCikis': toplam_cikis
            }
        else:
            print(f"'{ilac_adi_parcasi}' içeren ilaç bulunamadı!")
            return None

    except Exception as e:
        print(f"Hata: {e}")
        import traceback
        traceback.print_exc()
        return None


def karlilik_hesapla(maliyet: float, aylik_ort: float, mevcut_stok: int,
                     zam_tarihi: date, zam_orani: float, faiz_yillik: float,
                     depo_vade: int, max_miktar: int = None):
    """
    Her miktar için karlılık hesapla ve döndür.

    Returns:
        dict: {
            'miktarlar': [],
            'kazanclar': [],
            'roi_ler': [],
            'kritik_noktalar': {
                'verimlilik': {'miktar': x, 'kazanc': y, 'roi': z},
                'pareto': {...},
                'optimum': {...},
                'maksimum': {...}
            }
        }
    """
    bugun = date.today()
    zam_gun = (zam_tarihi - bugun).days

    if zam_gun <= 0 or aylik_ort <= 0 or maliyet <= 0:
        return None

    # Gün bazlı faiz
    aylik_faiz = (faiz_yillik / 100) / 12
    gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
    gunluk_sarf = aylik_ort / 30

    # Test aralığı
    if max_miktar is None:
        max_miktar = int(aylik_ort * 18)  # 18 aylık
    if max_miktar < 50:
        max_miktar = 200

    miktarlar = []
    kazanclar = []
    roi_ler = []
    yatirimlar = []

    for test_miktar in range(0, max_miktar + 1):
        if test_miktar == 0:
            miktarlar.append(0)
            kazanclar.append(0)
            roi_ler.append(0)
            yatirimlar.append(0)
            continue

        # Yatırım tutarı
        yatirim = test_miktar * maliyet

        kalan_mevcut = mevcut_stok
        kalan_yeni = test_miktar
        toplam_kazanc = 0

        gun = 0
        while kalan_yeni > 0 and gun < 720:  # Max 2 yıl
            harcanan = gunluk_sarf

            # Önce mevcut stoktan harca
            mevcut_harcanan = min(kalan_mevcut, harcanan)
            kalan_mevcut -= mevcut_harcanan
            yeni_harcanan = min(harcanan - mevcut_harcanan, kalan_yeni)

            if yeni_harcanan > 0:
                # Zam öncesi mi sonrası mı?
                if gun < zam_gun:
                    fiyat_o_gun = maliyet
                else:
                    fiyat_o_gun = maliyet * (1 + zam_orani / 100)

                # Ödeme günü (alımdan X gün sonra)
                odeme_gun = gun + depo_vade

                # Faiz maliyeti (paranın fırsat maliyeti)
                faiz_carpan = (1 + gunluk_faiz) ** odeme_gun

                # Kazanç = (Zamdan sonraki fiyat - Ödediğimiz fiyat) × miktar / faiz
                kazanc_birim = (fiyat_o_gun - maliyet) / faiz_carpan
                toplam_kazanc += kazanc_birim * yeni_harcanan

                kalan_yeni -= yeni_harcanan

            gun += 1

        miktarlar.append(test_miktar)
        kazanclar.append(toplam_kazanc)
        yatirimlar.append(yatirim)

        # ROI hesapla
        roi = (toplam_kazanc / yatirim * 100) if yatirim > 0 else 0
        roi_ler.append(roi)

    # Kritik noktaları bul
    kazanc_array = np.array(kazanclar)
    roi_array = np.array(roi_ler)

    # Maksimum kazanç (Optimum)
    optimum_idx = np.argmax(kazanc_array)
    optimum_miktar = miktarlar[optimum_idx]
    optimum_kazanc = kazanclar[optimum_idx]

    # Maksimum ROI (Verimlilik) - 0 hariç
    roi_nonzero = roi_array.copy()
    roi_nonzero[0] = -999  # 0'ı hariç tut
    verimlilik_idx = np.argmax(roi_nonzero)
    verimlilik_miktar = miktarlar[verimlilik_idx]
    verimlilik_kazanc = kazanclar[verimlilik_idx]
    verimlilik_roi = roi_ler[verimlilik_idx]

    # Pareto (%80 kazanç noktası)
    pareto_hedef = optimum_kazanc * 0.80
    pareto_idx = 0
    for i, k in enumerate(kazanclar):
        if k >= pareto_hedef:
            pareto_idx = i
            break
    pareto_miktar = miktarlar[pareto_idx]
    pareto_kazanc = kazanclar[pareto_idx]

    # Maksimum (karlılık sıfıra düştüğü nokta)
    maksimum_idx = len(miktarlar) - 1
    for i in range(optimum_idx, len(kazanclar)):
        if kazanclar[i] <= 0:
            maksimum_idx = i
            break
    maksimum_miktar = miktarlar[maksimum_idx]
    maksimum_kazanc = kazanclar[maksimum_idx]

    return {
        'miktarlar': miktarlar,
        'kazanclar': kazanclar,
        'roi_ler': roi_ler,
        'yatirimlar': yatirimlar,
        'kritik_noktalar': {
            'verimlilik': {
                'miktar': verimlilik_miktar,
                'kazanc': verimlilik_kazanc,
                'roi': verimlilik_roi,
                'idx': verimlilik_idx
            },
            'pareto': {
                'miktar': pareto_miktar,
                'kazanc': pareto_kazanc,
                'roi': roi_ler[pareto_idx] if pareto_idx < len(roi_ler) else 0,
                'idx': pareto_idx
            },
            'optimum': {
                'miktar': optimum_miktar,
                'kazanc': optimum_kazanc,
                'roi': roi_ler[optimum_idx] if optimum_idx < len(roi_ler) else 0,
                'idx': optimum_idx
            },
            'maksimum': {
                'miktar': maksimum_miktar,
                'kazanc': maksimum_kazanc,
                'roi': roi_ler[maksimum_idx] if maksimum_idx < len(roi_ler) else 0,
                'idx': maksimum_idx
            }
        }
    }


def grafik_ciz(ilac_bilgi: dict, sonuc: dict, zam_orani: float, zam_tarihi: date,
               faiz: float, dosya_adi: str = None):
    """Karlılık grafiğini çiz"""

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])
    fig.suptitle(f"Zam Öncesi Sipariş Karlılık Analizi\n{ilac_bilgi['UrunAdi']}",
                 fontsize=14, fontweight='bold', y=0.98)

    miktarlar = sonuc['miktarlar']
    kazanclar = sonuc['kazanclar']
    roi_ler = sonuc['roi_ler']
    kn = sonuc['kritik_noktalar']

    # ===== ÜST GRAFİK: KAZANÇ EĞRİSİ =====
    ax1.fill_between(miktarlar, kazanclar, alpha=0.3, color='green',
                     where=[k >= 0 for k in kazanclar], label='Kâr bölgesi')
    ax1.fill_between(miktarlar, kazanclar, alpha=0.3, color='red',
                     where=[k < 0 for k in kazanclar], label='Zarar bölgesi')
    ax1.plot(miktarlar, kazanclar, 'b-', linewidth=2, label='Kazanç eğrisi')
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # Kritik noktaları işaretle
    colors = {'verimlilik': '#FF9800', 'pareto': '#4CAF50', 'optimum': '#2196F3', 'maksimum': '#F44336'}
    markers = {'verimlilik': 'D', 'pareto': 's', 'optimum': '^', 'maksimum': 'X'}
    labels = {'verimlilik': 'Maks. ROI', 'pareto': 'Pareto (%80)', 'optimum': 'Maks. Kazanç', 'maksimum': 'Sınır'}

    for nokta_adi, nokta in kn.items():
        ax1.scatter(nokta['miktar'], nokta['kazanc'],
                   c=colors[nokta_adi], s=150, marker=markers[nokta_adi],
                   zorder=5, edgecolors='black', linewidths=1)

        # Etiket
        offset_y = nokta['kazanc'] * 0.1 if nokta['kazanc'] > 0 else -50
        ax1.annotate(
            f"{labels[nokta_adi]}\n{nokta['miktar']} adet\n{nokta['kazanc']:,.0f} TL",
            xy=(nokta['miktar'], nokta['kazanc']),
            xytext=(nokta['miktar'], nokta['kazanc'] + offset_y + 100),
            fontsize=9, ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=colors[nokta_adi], alpha=0.7),
            arrowprops=dict(arrowstyle='->', color='gray')
        )

    # Mevcut stok çizgisi
    stok = ilac_bilgi['Stok']
    if stok > 0 and stok < max(miktarlar):
        ax1.axvline(x=stok, color='purple', linestyle='--', linewidth=1.5, alpha=0.7)
        ax1.text(stok, max(kazanclar) * 0.9, f'  Mevcut Stok: {stok}',
                fontsize=9, color='purple', rotation=90, va='top')

    ax1.set_xlabel('Sipariş Miktarı (adet)', fontsize=11)
    ax1.set_ylabel('Net Kazanç (TL)', fontsize=11)
    ax1.set_title('Sipariş Miktarına Göre Net Kazanç', fontsize=12, pad=10)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')

    # Y ekseni formatı
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:,.0f}'))

    # ===== ALT GRAFİK: ROI EĞRİSİ =====
    ax2.plot(miktarlar, roi_ler, 'g-', linewidth=2, label='ROI %')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # Kritik noktaları ROI grafiğinde de göster
    for nokta_adi, nokta in kn.items():
        if nokta['idx'] < len(roi_ler):
            ax2.scatter(nokta['miktar'], nokta['roi'],
                       c=colors[nokta_adi], s=100, marker=markers[nokta_adi],
                       zorder=5, edgecolors='black', linewidths=1)

    ax2.set_xlabel('Sipariş Miktarı (adet)', fontsize=11)
    ax2.set_ylabel('ROI (%)', fontsize=11)
    ax2.set_title('Sipariş Miktarına Göre Yatırım Getirisi (ROI)', fontsize=12, pad=10)
    ax2.grid(True, alpha=0.3)

    # ===== BİLGİ KUTUSU =====
    bilgi_text = (
        f"İlaç: {ilac_bilgi['UrunAdi']}\n"
        f"Depocu Fiyat: {ilac_bilgi['DepocuFiyat']:,.2f} TL\n"
        f"Aylık Ort. Satış: {ilac_bilgi['AylikOrt']:.1f} adet\n"
        f"Mevcut Stok: {ilac_bilgi['Stok']} adet\n"
        f"─────────────────────\n"
        f"Zam Oranı: %{zam_orani}\n"
        f"Zam Tarihi: {zam_tarihi.strftime('%d.%m.%Y')}\n"
        f"Zama Kalan: {(zam_tarihi - date.today()).days} gün\n"
        f"Faiz: %{faiz} (yıllık)\n"
        f"─────────────────────\n"
        f"Öneriler:\n"
        f"  • Maks.ROI: {kn['verimlilik']['miktar']} ad. ({kn['verimlilik']['kazanc']:,.0f} TL)\n"
        f"  • Pareto: {kn['pareto']['miktar']} ad. ({kn['pareto']['kazanc']:,.0f} TL)\n"
        f"  • Maks.Kazanç: {kn['optimum']['miktar']} ad. ({kn['optimum']['kazanc']:,.0f} TL)"
    )

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    fig.text(0.02, 0.02, bilgi_text, fontsize=9, verticalalignment='bottom',
             bbox=props, family='monospace')

    # Legend için özel işaretler
    legend_elements = [
        mpatches.Patch(color=colors['verimlilik'], label=f"Maks. ROI: {kn['verimlilik']['miktar']} adet"),
        mpatches.Patch(color=colors['pareto'], label=f"Pareto (%80): {kn['pareto']['miktar']} adet"),
        mpatches.Patch(color=colors['optimum'], label=f"Maks. Kazanç: {kn['optimum']['miktar']} adet"),
        mpatches.Patch(color=colors['maksimum'], label=f"Sınır: {kn['maksimum']['miktar']} adet"),
    ]
    fig.legend(handles=legend_elements, loc='lower right', fontsize=9,
               bbox_to_anchor=(0.98, 0.02))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.18, top=0.92)

    if dosya_adi:
        plt.savefig(dosya_adi, dpi=150, bbox_inches='tight')
        print(f"Grafik kaydedildi: {dosya_adi}")

    plt.show()


def main():
    """Ana fonksiyon"""
    # Parametreler
    ZAM_ORANI = 25  # %25 zam beklentisi
    ZAM_TARIHI = date(2026, 3, 1)  # Zam tarihi (yaklaşık 1 ay sonrası)
    FAIZ_YILLIK = 45  # %45 yıllık faiz
    DEPO_VADE = 75  # 75 gün vade

    ilaclar = [
        ("ARVELES", "zam_karlilik_arveles.png"),
        ("AMOKLAVIN BID 1000MG 10", "zam_karlilik_amoklavin.png")
    ]

    for ilac_adi, dosya_adi in ilaclar:
        print(f"\n{'='*50}")
        print(f"İlaç: {ilac_adi}")
        print('='*50)

        # Veritabanından bilgi al
        ilac_bilgi = veritabanindan_ilac_bilgisi_al(ilac_adi)

        if ilac_bilgi is None:
            print(f"'{ilac_adi}' için veri bulunamadı, atlanıyor...")
            continue

        print(f"Bulunan: {ilac_bilgi['UrunAdi']}")
        print(f"  Depocu Fiyat: {ilac_bilgi['DepocuFiyat']:.2f} TL")
        print(f"  Aylık Ort: {ilac_bilgi['AylikOrt']:.1f} adet")
        print(f"  Stok: {ilac_bilgi['Stok']} adet")

        # Karlılık hesapla
        sonuc = karlilik_hesapla(
            maliyet=ilac_bilgi['DepocuFiyat'],
            aylik_ort=ilac_bilgi['AylikOrt'],
            mevcut_stok=ilac_bilgi['Stok'],
            zam_tarihi=ZAM_TARIHI,
            zam_orani=ZAM_ORANI,
            faiz_yillik=FAIZ_YILLIK,
            depo_vade=DEPO_VADE
        )

        if sonuc is None:
            print("Karlılık hesaplanamadı!")
            continue

        kn = sonuc['kritik_noktalar']
        print(f"\nKritik Noktalar:")
        print(f"  Maks.ROI (Verimlilik): {kn['verimlilik']['miktar']} adet => {kn['verimlilik']['kazanc']:,.0f} TL kazanc, ROI: %{kn['verimlilik']['roi']:.1f}")
        print(f"  Pareto (%80 Kazanc): {kn['pareto']['miktar']} adet => {kn['pareto']['kazanc']:,.0f} TL kazanc")
        print(f"  Maks.Kazanc (Optimum): {kn['optimum']['miktar']} adet => {kn['optimum']['kazanc']:,.0f} TL kazanc")
        print(f"  Sinir (Negatife Donus): {kn['maksimum']['miktar']} adet")

        # Grafik çiz
        grafik_ciz(ilac_bilgi, sonuc, ZAM_ORANI, ZAM_TARIHI, FAIZ_YILLIK, dosya_adi)


if __name__ == "__main__":
    main()
