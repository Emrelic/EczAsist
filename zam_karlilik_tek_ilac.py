"""
Zam Karlılık Grafiği - Tek İlaç Detaylı Görünüm
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import numpy as np
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


def veritabanindan_ilac_bilgisi_al(ilac_adi_parcasi: str):
    """Veritabanından ilaç bilgilerini çek"""
    try:
        from botanik_db import BotanikDB
        db = BotanikDB()
        if not db.baglan():
            return None

        bugun = datetime.now()
        baslangic = (bugun - relativedelta(months=6)).strftime('%Y-%m-%d')

        sql = f"""
        ;WITH CikisVerileri AS (
            SELECT ri.RIUrunId as UrunId, ri.RIAdet as Adet
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            AND ra.RxKayitTarihi >= '{baslangic}'
            UNION ALL
            SELECT ei.RIUrunId as UrunId, ei.RIAdet as Adet
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            AND ea.RxKayitTarihi >= '{baslangic}'
        )
        SELECT TOP 1
            u.UrunId, u.UrunAdi,
            COALESCE(u.UrunFiyatEtiket, 0) as PSF,
            COALESCE(u.UrunIskontoKamu, 0) as IskontoKamu,
            CASE WHEN u.UrunUrunTipId IN (1, 16) THEN
                (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1)
            ELSE (COALESCE(u.UrunStokDepo,0) + COALESCE(u.UrunStokRaf,0) + COALESCE(u.UrunStokAcik,0))
            END as Stok,
            COALESCE((SELECT SUM(Adet) FROM CikisVerileri WHERE UrunId = u.UrunId), 0) as ToplamCikis
        FROM Urun u
        WHERE u.UrunSilme = 0 AND u.UrunAdi LIKE '%{ilac_adi_parcasi}%' AND u.UrunUrunTipId IN (1, 16)
        ORDER BY CASE WHEN u.UrunAdi LIKE '{ilac_adi_parcasi}%' THEN 0 ELSE 1 END,
            (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1) DESC
        """
        sonuclar = db.sorgu_calistir(sql)
        db.kapat()

        if sonuclar:
            veri = sonuclar[0]
            psf = float(veri.get('PSF', 0) or 0)
            iskonto = float(veri.get('IskontoKamu', 0) or 0)
            depocu_fiyat = psf * 0.71 * 1.10 * (1 - iskonto / 100) if psf > 0 else 0
            toplam_cikis = float(veri.get('ToplamCikis', 0) or 0)
            return {
                'UrunId': veri.get('UrunId'),
                'UrunAdi': veri.get('UrunAdi'),
                'PSF': psf,
                'IskontoKamu': iskonto,
                'DepocuFiyat': depocu_fiyat,
                'Stok': int(veri.get('Stok', 0) or 0),
                'AylikOrt': toplam_cikis / 6,
                'ToplamCikis': toplam_cikis
            }
        return None
    except Exception as e:
        print(f"Hata: {e}")
        return None


def karlilik_hesapla(maliyet: float, aylik_ort: float, mevcut_stok: int,
                     zam_tarihi: date, zam_orani: float, faiz_yillik: float,
                     depo_vade: int, max_miktar: int = None):
    """Karlılık hesapla - tüm kritik noktalarla birlikte"""
    bugun = date.today()
    zam_gun = (zam_tarihi - bugun).days

    if zam_gun <= 0 or aylik_ort <= 0 or maliyet <= 0:
        return None

    aylik_faiz = (faiz_yillik / 100) / 12
    gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
    gunluk_sarf = aylik_ort / 30

    if max_miktar is None:
        max_miktar = int(aylik_ort * 12)
    if max_miktar < 50:
        max_miktar = 200

    siparis_miktarlari = []
    kazanclar = []
    roi_ler = []

    for test_miktar in range(0, max_miktar + 1):
        if test_miktar == 0:
            siparis_miktarlari.append(0)
            kazanclar.append(0)
            roi_ler.append(0)
            continue

        kalan_mevcut = mevcut_stok
        kalan_yeni = test_miktar
        npv_aylik = 0

        gun = 0
        while kalan_yeni > 0 and gun < 720:
            harcanan = gunluk_sarf
            mevcut_harcanan = min(kalan_mevcut, harcanan)
            kalan_mevcut -= mevcut_harcanan
            yeni_harcanan = min(harcanan - mevcut_harcanan, kalan_yeni)

            if yeni_harcanan > 0:
                fiyat = maliyet if gun < zam_gun else maliyet * (1 + zam_orani / 100)
                ay_sonu = ((gun // 30) + 1) * 30
                odeme_gun = ay_sonu + depo_vade
                iskonto = (1 + gunluk_faiz) ** odeme_gun
                npv_aylik += (yeni_harcanan * fiyat) / iskonto
                kalan_yeni -= yeni_harcanan
            gun += 1

        npv_toplu = (test_miktar * maliyet) / ((1 + gunluk_faiz) ** (30 + depo_vade))
        kazanc = npv_aylik - npv_toplu

        siparis_miktarlari.append(test_miktar)
        kazanclar.append(kazanc)
        yatirim = test_miktar * maliyet
        roi_ler.append((kazanc / yatirim * 100) if yatirim > 0 else 0)

    # Marjinal kazançlar
    marjinal_kazanclar = [0]
    for i in range(1, len(kazanclar)):
        marjinal_kazanclar.append(kazanclar[i] - kazanclar[i-1])

    # Kritik noktalar
    kazanc_array = np.array(kazanclar)
    roi_array = np.array(roi_ler)

    optimum_idx = np.argmax(kazanc_array)

    roi_nonzero = roi_array.copy()
    roi_nonzero[0] = -999
    max_roi_idx = np.argmax(roi_nonzero)

    pareto_hedef = kazanclar[optimum_idx] * 0.80
    pareto_idx = 0
    for i, k in enumerate(kazanclar):
        if k >= pareto_hedef:
            pareto_idx = i
            break

    negatif_idx = 0
    for i, k in enumerate(kazanclar):
        if k > 0:
            negatif_idx = i
    if negatif_idx < len(kazanclar) - 1:
        negatif_idx += 1

    # Azalan verimlilik
    max_marjinal = max(marjinal_kazanclar[1:]) if len(marjinal_kazanclar) > 1 else 0
    azalan_idx = 1
    for i, m in enumerate(marjinal_kazanclar):
        if m == max_marjinal:
            azalan_idx = i
            break

    yarim_marjinal = max_marjinal * 0.5
    azalan_yarim_idx = azalan_idx
    for i in range(azalan_idx, len(marjinal_kazanclar)):
        if marjinal_kazanclar[i] <= yarim_marjinal:
            azalan_yarim_idx = i
            break

    return {
        'siparis_miktarlari': siparis_miktarlari,
        'kazanclar': kazanclar,
        'roi_ler': roi_ler,
        'marjinal_kazanclar': marjinal_kazanclar,
        'mevcut_stok': mevcut_stok,
        'kritik_noktalar': {
            'max_roi': {'miktar': siparis_miktarlari[max_roi_idx], 'kazanc': kazanclar[max_roi_idx],
                       'roi': roi_ler[max_roi_idx], 'idx': max_roi_idx},
            'azalan_verim': {'miktar': siparis_miktarlari[azalan_yarim_idx], 'kazanc': kazanclar[azalan_yarim_idx],
                            'marjinal': marjinal_kazanclar[azalan_yarim_idx], 'idx': azalan_yarim_idx},
            'pareto': {'miktar': siparis_miktarlari[pareto_idx], 'kazanc': kazanclar[pareto_idx], 'idx': pareto_idx},
            'optimum': {'miktar': siparis_miktarlari[optimum_idx], 'kazanc': kazanclar[optimum_idx], 'idx': optimum_idx},
            'negatif': {'miktar': siparis_miktarlari[negatif_idx], 'kazanc': kazanclar[negatif_idx], 'idx': negatif_idx}
        }
    }


def tek_ilac_grafik_ciz(ilac_bilgi: dict, sonuc: dict, zam_orani: float,
                        zam_tarihi: date, faiz: float, dosya_adi: str = None):
    """Tek ilaç için detaylı tam ekran grafik"""

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), height_ratios=[2.5, 1])

    zam_gun = (zam_tarihi - date.today()).days

    fig.suptitle(f"Zam Oncesi Siparis Karlilik Analizi\n{ilac_bilgi['UrunAdi']}",
                 fontsize=16, fontweight='bold', y=0.98)

    miktarlar = sonuc['siparis_miktarlari']
    kazanclar = sonuc['kazanclar']
    roi_ler = sonuc['roi_ler']
    marjinal = sonuc['marjinal_kazanclar']
    kn = sonuc['kritik_noktalar']
    stok = sonuc['mevcut_stok']

    colors = {
        'max_roi': '#FF9800',
        'azalan_verim': '#9C27B0',
        'pareto': '#4CAF50',
        'optimum': '#2196F3',
        'negatif': '#F44336'
    }
    markers = {'max_roi': 'D', 'azalan_verim': 'p', 'pareto': 's', 'optimum': '^', 'negatif': 'X'}
    labels = {
        'max_roi': 'Maks. ROI',
        'azalan_verim': 'Azalan Verim',
        'pareto': 'Pareto (%80)',
        'optimum': 'Tepe (Pik)',
        'negatif': 'Negatife Donus'
    }

    # ===== ÜST GRAFİK: KAZANÇ EĞRİSİ =====
    ax1.fill_between(miktarlar, kazanclar, alpha=0.3, color='green', where=[k >= 0 for k in kazanclar])
    ax1.fill_between(miktarlar, kazanclar, alpha=0.3, color='red', where=[k < 0 for k in kazanclar])
    ax1.plot(miktarlar, kazanclar, 'b-', linewidth=2.5, label='Kazanc Egrisi')
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=1)

    # Mevcut stok çizgisi
    if stok > 0 and stok < max(miktarlar):
        ax1.axvline(x=stok, color='gray', linestyle='--', linewidth=2, alpha=0.7)
        ax1.text(stok + 5, max(kazanclar) * 0.9, f'Mevcut Stok: {stok} ad.',
                fontsize=10, color='gray', rotation=90, va='top')

    # Kritik noktaları işaretle
    for nokta_adi, nokta in kn.items():
        ax1.scatter(nokta['miktar'], nokta['kazanc'], c=colors[nokta_adi],
                   s=200, marker=markers[nokta_adi], zorder=5, edgecolors='black', linewidths=1.5)

        # Dikey çizgi
        ax1.axvline(x=nokta['miktar'], color=colors[nokta_adi], linestyle=':', linewidth=1, alpha=0.5)

        # Etiket
        offset_y = max(kazanclar) * 0.08
        if nokta_adi == 'negatif':
            offset_y = -offset_y * 2

        roi_text = f"\nROI: %{nokta.get('roi', 0):.1f}" if 'roi' in nokta else ""
        marj_text = f"\nMarj: {nokta.get('marjinal', 0):.2f} TL/ad" if 'marjinal' in nokta else ""

        ax1.annotate(
            f"{labels[nokta_adi]}\n{nokta['miktar']} adet\n{nokta['kazanc']:,.0f} TL{roi_text}{marj_text}",
            xy=(nokta['miktar'], nokta['kazanc']),
            xytext=(nokta['miktar'], nokta['kazanc'] + offset_y),
            fontsize=9, ha='center', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=colors[nokta_adi], alpha=0.8, edgecolor='black'),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5)
        )

    ax1.set_xlabel('Siparis Miktari (adet)', fontsize=12)
    ax1.set_ylabel('Net Kazanc (TL)', fontsize=12)
    ax1.set_title('Siparis Miktarina Gore Net Kazanc', fontsize=13, pad=10)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:,.0f}'))

    # ===== ALT GRAFİK: ROI ve MARJİNAL =====
    ax2_twin = ax2.twinx()

    # ROI eğrisi (sol eksen)
    line1, = ax2.plot(miktarlar, roi_ler, 'g-', linewidth=2, label='ROI (%)')
    ax2.set_ylabel('ROI (%)', color='green', fontsize=11)
    ax2.tick_params(axis='y', labelcolor='green')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # Marjinal kazanç (sağ eksen)
    line2, = ax2_twin.plot(miktarlar, marjinal, 'orange', linewidth=2, linestyle='--', label='Marjinal Kazanc (TL/ad)')
    ax2_twin.set_ylabel('Marjinal Kazanc (TL/adet)', color='orange', fontsize=11)
    ax2_twin.tick_params(axis='y', labelcolor='orange')
    ax2_twin.axhline(y=0, color='orange', linestyle=':', linewidth=0.5, alpha=0.5)

    # Kritik noktaları alt grafikte de göster
    for nokta_adi, nokta in kn.items():
        idx = nokta['idx']
        if idx < len(roi_ler):
            ax2.scatter(nokta['miktar'], roi_ler[idx], c=colors[nokta_adi], s=100,
                       marker=markers[nokta_adi], zorder=5, edgecolors='black')

    ax2.set_xlabel('Siparis Miktari (adet)', fontsize=12)
    ax2.set_title('ROI ve Marjinal Kazanc Egrileri', fontsize=13, pad=10)
    ax2.grid(True, alpha=0.3)
    ax2.legend([line1, line2], ['ROI (%)', 'Marjinal Kazanc (TL/ad)'], loc='upper right')

    # ===== BİLGİ KUTUSU =====
    bilgi_text = (
        f"Ilac: {ilac_bilgi['UrunAdi']}\n"
        f"Depocu Fiyat: {ilac_bilgi['DepocuFiyat']:,.2f} TL\n"
        f"Aylik Ort. Satis: {ilac_bilgi['AylikOrt']:.1f} adet\n"
        f"Mevcut Stok: {ilac_bilgi['Stok']} adet\n"
        f"{'─'*30}\n"
        f"Zam Orani: %{zam_orani}\n"
        f"Zam Tarihi: {zam_tarihi.strftime('%d.%m.%Y')}\n"
        f"Zama Kalan: {zam_gun} gun\n"
        f"Faiz: %{faiz} (yillik)\n"
        f"{'─'*30}\n"
        f"ONERILER:\n"
        f"  Maks.ROI: {kn['max_roi']['miktar']} ad. ({kn['max_roi']['kazanc']:,.0f} TL)\n"
        f"  Azalan Verim: {kn['azalan_verim']['miktar']} ad.\n"
        f"  Pareto %80: {kn['pareto']['miktar']} ad. ({kn['pareto']['kazanc']:,.0f} TL)\n"
        f"  Tepe (Pik): {kn['optimum']['miktar']} ad. ({kn['optimum']['kazanc']:,.0f} TL)\n"
        f"  Sinir: {kn['negatif']['miktar']} ad."
    )

    props = dict(boxstyle='round', facecolor='lightyellow', alpha=0.9, edgecolor='black')
    fig.text(0.01, 0.01, bilgi_text, fontsize=9, verticalalignment='bottom',
             bbox=props, family='monospace')

    # Legend
    legend_elements = [
        mpatches.Patch(color=colors['max_roi'], label='Maks. ROI (En verimli)'),
        mpatches.Patch(color=colors['azalan_verim'], label='Azalan Verim (Marjinal %50)'),
        mpatches.Patch(color=colors['pareto'], label='Pareto (%80 kazanc)'),
        mpatches.Patch(color=colors['optimum'], label='Tepe (Maks. mutlak kazanc)'),
        mpatches.Patch(color=colors['negatif'], label='Negatife Donus (Sinir)'),
    ]
    fig.legend(handles=legend_elements, loc='lower right', fontsize=9, bbox_to_anchor=(0.99, 0.01))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.22, top=0.92, hspace=0.25)

    if dosya_adi:
        plt.savefig(dosya_adi, dpi=150, bbox_inches='tight')
        print(f"Grafik kaydedildi: {dosya_adi}")

    plt.close(fig)
    return dosya_adi


def main():
    ZAM_ORANI = 25
    ZAM_TARIHI = date(2026, 3, 1)
    FAIZ_YILLIK = 45
    DEPO_VADE = 75

    ilac_adi = "ARVELES"

    print(f"Ilac aranıyor: {ilac_adi}")
    ilac_bilgi = veritabanindan_ilac_bilgisi_al(ilac_adi)

    if ilac_bilgi is None:
        print("Ilac bulunamadi!")
        return

    print(f"Bulunan: {ilac_bilgi['UrunAdi']}")
    print(f"  Depocu Fiyat: {ilac_bilgi['DepocuFiyat']:.2f} TL")
    print(f"  Aylik Ort: {ilac_bilgi['AylikOrt']:.1f} adet")
    print(f"  Stok: {ilac_bilgi['Stok']} adet")

    sonuc = karlilik_hesapla(
        maliyet=ilac_bilgi['DepocuFiyat'],
        aylik_ort=ilac_bilgi['AylikOrt'],
        mevcut_stok=ilac_bilgi['Stok'],
        zam_tarihi=ZAM_TARIHI,
        zam_orani=ZAM_ORANI,
        faiz_yillik=FAIZ_YILLIK,
        depo_vade=DEPO_VADE
    )

    if sonuc:
        kn = sonuc['kritik_noktalar']
        print(f"\nKritik Noktalar:")
        for k, v in kn.items():
            print(f"  {k}: {v['miktar']} adet => {v['kazanc']:,.0f} TL")

        tek_ilac_grafik_ciz(ilac_bilgi, sonuc, ZAM_ORANI, ZAM_TARIHI, FAIZ_YILLIK,
                           "zam_karlilik_arveles_detay.png")


if __name__ == "__main__":
    main()
