"""
Zam ROI Analizi - Her 100 TL yatırımda kazanç
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


def roi_bazli_hesapla(maliyet: float, aylik_ort: float, mevcut_stok: int,
                      zam_tarihi: date, zam_orani: float, faiz_yillik: float,
                      depo_vade: int, max_miktar: int = None):
    """
    ROI bazlı karlılık hesabı - Her 100 TL yatırımda kazanç
    """
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

    miktarlar = []
    kazanclar = []
    yatirimlar = []
    roi_ler = []  # Her 100 TL'de kazanç (%)
    marjinal_roi = []  # Her ek birim için ROI

    for test_miktar in range(0, max_miktar + 1):
        if test_miktar == 0:
            miktarlar.append(0)
            kazanclar.append(0)
            yatirimlar.append(0)
            roi_ler.append(0)
            marjinal_roi.append(0)
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
        yatirim = test_miktar * maliyet

        miktarlar.append(test_miktar)
        kazanclar.append(kazanc)
        yatirimlar.append(yatirim)

        # ROI = Kazanç / Yatırım × 100 (her 100 TL'de kazanç)
        roi = (kazanc / yatirim * 100) if yatirim > 0 else 0
        roi_ler.append(roi)

        # Marjinal ROI (bu birim için ROI)
        if test_miktar > 1:
            ek_kazanc = kazanc - kazanclar[-2]
            ek_yatirim = maliyet
            m_roi = (ek_kazanc / ek_yatirim * 100) if ek_yatirim > 0 else 0
            marjinal_roi.append(m_roi)
        else:
            marjinal_roi.append(roi)

    # Kritik noktalar
    roi_arr = np.array(roi_ler)
    kazanc_arr = np.array(kazanclar)

    # Maksimum ROI
    roi_arr_copy = roi_arr.copy()
    roi_arr_copy[0] = -999
    max_roi_idx = np.argmax(roi_arr_copy)

    # ROI'nin yarıya düştüğü nokta
    max_roi_val = roi_ler[max_roi_idx]
    yarim_roi_idx = max_roi_idx
    for i in range(max_roi_idx, len(roi_ler)):
        if roi_ler[i] <= max_roi_val / 2:
            yarim_roi_idx = i
            break

    # ROI sıfıra düştüğü nokta
    sifir_roi_idx = len(roi_ler) - 1
    for i in range(max_roi_idx, len(roi_ler)):
        if roi_ler[i] <= 0:
            sifir_roi_idx = i
            break

    # Pareto (%80 kazanç noktası)
    optimum_idx = np.argmax(kazanc_arr)
    pareto_hedef = kazanclar[optimum_idx] * 0.80
    pareto_idx = next((i for i, k in enumerate(kazanclar) if k >= pareto_hedef), 0)

    return {
        'miktarlar': miktarlar,
        'kazanclar': kazanclar,
        'yatirimlar': yatirimlar,
        'roi_ler': roi_ler,
        'marjinal_roi': marjinal_roi,
        'mevcut_stok': mevcut_stok,
        'kritik': {
            'max_roi': {'m': miktarlar[max_roi_idx], 'k': kazanclar[max_roi_idx],
                       'y': yatirimlar[max_roi_idx], 'r': roi_ler[max_roi_idx], 'i': max_roi_idx},
            'yarim_roi': {'m': miktarlar[yarim_roi_idx], 'k': kazanclar[yarim_roi_idx],
                         'y': yatirimlar[yarim_roi_idx], 'r': roi_ler[yarim_roi_idx], 'i': yarim_roi_idx},
            'pareto': {'m': miktarlar[pareto_idx], 'k': kazanclar[pareto_idx],
                      'y': yatirimlar[pareto_idx], 'r': roi_ler[pareto_idx], 'i': pareto_idx},
            'optimum': {'m': miktarlar[optimum_idx], 'k': kazanclar[optimum_idx],
                       'y': yatirimlar[optimum_idx], 'r': roi_ler[optimum_idx], 'i': optimum_idx},
            'sifir_roi': {'m': miktarlar[sifir_roi_idx], 'k': kazanclar[sifir_roi_idx],
                         'y': yatirimlar[sifir_roi_idx], 'r': roi_ler[sifir_roi_idx], 'i': sifir_roi_idx}
        }
    }


def roi_grafik_ciz(ilac: dict, sonuc: dict, zam_orani: float, zam_tarihi: date,
                   faiz: float, dosya_adi: str = None):
    """ROI bazlı grafik - Her 100 TL'de kazanç"""

    zam_gun = (zam_tarihi - date.today()).days

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f"ROI Bazli Zam Analizi - Her 100 TL Yatirimda Kazanc\n{ilac['UrunAdi']}",
                 fontsize=14, fontweight='bold', y=0.98)

    m = sonuc['miktarlar']
    k = sonuc['kazanclar']
    y = sonuc['yatirimlar']
    r = sonuc['roi_ler']
    mr = sonuc['marjinal_roi']
    kn = sonuc['kritik']
    stok = sonuc['mevcut_stok']

    colors = {
        'max_roi': '#FF9800',
        'yarim_roi': '#9C27B0',
        'pareto': '#4CAF50',
        'optimum': '#2196F3',
        'sifir_roi': '#F44336'
    }
    labels = {
        'max_roi': f"Maks ROI: %{kn['max_roi']['r']:.1f}",
        'yarim_roi': f"ROI Yariya Dustu: %{kn['yarim_roi']['r']:.1f}",
        'pareto': f"Pareto %80: %{kn['pareto']['r']:.1f}",
        'optimum': f"Tepe (Maks Kar): %{kn['optimum']['r']:.1f}",
        'sifir_roi': f"ROI Sifir: %{kn['sifir_roi']['r']:.1f}"
    }

    # ===== GRAFIK 1: ROI Egrisi (Ana Grafik) =====
    ax1 = axes[0, 0]
    ax1.fill_between(m, r, alpha=0.3, color='green', where=[x >= 0 for x in r])
    ax1.fill_between(m, r, alpha=0.3, color='red', where=[x < 0 for x in r])
    ax1.plot(m, r, 'b-', linewidth=2.5, label='ROI (%)')
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=1)

    # Kritik noktalar
    for n, v in kn.items():
        ax1.scatter(v['m'], v['r'], c=colors[n], s=150, marker='o', zorder=5, edgecolors='black', linewidths=1.5)
        ax1.axvline(x=v['m'], color=colors[n], linestyle=':', linewidth=1, alpha=0.5)

    if stok > 0 and stok < max(m):
        ax1.axvline(x=stok, color='gray', linestyle='--', linewidth=2, alpha=0.7)

    ax1.set_xlabel('Siparis Miktari (adet)', fontsize=11)
    ax1.set_ylabel('ROI - Her 100 TL\'de Kazanc (%)', fontsize=11)
    ax1.set_title('Siparis Miktarina Gore ROI', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # ===== GRAFIK 2: Yatirim vs Kazanc =====
    ax2 = axes[0, 1]

    # X ekseni: Yatırım (TL), Y ekseni: Kazanç (TL)
    ax2.fill_between(y, k, alpha=0.3, color='green', where=[x >= 0 for x in k])
    ax2.fill_between(y, k, alpha=0.3, color='red', where=[x < 0 for x in k])
    ax2.plot(y, k, 'b-', linewidth=2.5)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)

    for n, v in kn.items():
        ax2.scatter(v['y'], v['k'], c=colors[n], s=150, marker='o', zorder=5, edgecolors='black', linewidths=1.5)

    ax2.set_xlabel('Yatirim (TL)', fontsize=11)
    ax2.set_ylabel('Net Kazanc (TL)', fontsize=11)
    ax2.set_title('Yatirim vs Kazanc', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:,.0f}'))

    # ===== GRAFIK 3: Marjinal ROI =====
    ax3 = axes[1, 0]
    ax3.fill_between(m, mr, alpha=0.3, color='orange', where=[x >= 0 for x in mr])
    ax3.fill_between(m, mr, alpha=0.3, color='red', where=[x < 0 for x in mr])
    ax3.plot(m, mr, 'orange', linewidth=2)
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=1)

    for n, v in kn.items():
        if v['i'] < len(mr):
            ax3.scatter(v['m'], mr[v['i']], c=colors[n], s=100, marker='o', zorder=5, edgecolors='black')

    ax3.set_xlabel('Siparis Miktari (adet)', fontsize=11)
    ax3.set_ylabel('Marjinal ROI - Ek 1 Birim icin (%)', fontsize=11)
    ax3.set_title('Marjinal ROI (Her Ek Birim icin Getiri)', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    # ===== GRAFIK 4: Ozet Tablo =====
    ax4 = axes[1, 1]
    ax4.axis('off')

    # Bilgi tablosu
    tablo_text = f"""
╔══════════════════════════════════════════════════════════════╗
║  ARVELES - ROI BAZLI ZAM ANALIZI                             ║
╠══════════════════════════════════════════════════════════════╣
║  Depocu Fiyat: {ilac['DepocuFiyat']:>10.2f} TL                         ║
║  Aylik Satis:  {ilac['AylikOrt']:>10.0f} adet                        ║
║  Mevcut Stok:  {stok:>10} adet                        ║
║  Zam Orani:    {zam_orani:>10.0f} %                           ║
║  Zama Kalan:   {zam_gun:>10} gun                          ║
║  Faiz:         {faiz:>10.0f} % (yillik)                   ║
╠══════════════════════════════════════════════════════════════╣
║  KRITIK NOKTALAR (Her 100 TL'de Kazanc)                      ║
╠══════════════════════════════════════════════════════════════╣
║  Maks ROI:     +{kn['max_roi']['m']:>4} ad. => {kn['max_roi']['k']:>8,.0f} TL  [%{kn['max_roi']['r']:>5.1f}]  ║
║                Yatirim: {kn['max_roi']['y']:>10,.0f} TL                    ║
║                Her 100 TL'de {kn['max_roi']['r']:.2f} TL kazanc            ║
╠──────────────────────────────────────────────────────────────╣
║  ROI %50:      +{kn['yarim_roi']['m']:>4} ad. => {kn['yarim_roi']['k']:>8,.0f} TL  [%{kn['yarim_roi']['r']:>5.1f}]  ║
║                Yatirim: {kn['yarim_roi']['y']:>10,.0f} TL                    ║
╠──────────────────────────────────────────────────────────────╣
║  Pareto %80:   +{kn['pareto']['m']:>4} ad. => {kn['pareto']['k']:>8,.0f} TL  [%{kn['pareto']['r']:>5.1f}]  ║
║                Yatirim: {kn['pareto']['y']:>10,.0f} TL                    ║
╠──────────────────────────────────────────────────────────────╣
║  Tepe (Pik):   +{kn['optimum']['m']:>4} ad. => {kn['optimum']['k']:>8,.0f} TL  [%{kn['optimum']['r']:>5.1f}]  ║
║                Yatirim: {kn['optimum']['y']:>10,.0f} TL                    ║
╠──────────────────────────────────────────────────────────────╣
║  ROI Sifir:    +{kn['sifir_roi']['m']:>4} ad. => {kn['sifir_roi']['k']:>8,.0f} TL  [%{kn['sifir_roi']['r']:>5.1f}]  ║
║                Yatirim: {kn['sifir_roi']['y']:>10,.0f} TL                    ║
╚══════════════════════════════════════════════════════════════╝
"""
    ax4.text(0.05, 0.95, tablo_text, transform=ax4.transAxes, fontsize=9,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

    # Legend
    legend_el = [mpatches.Patch(color=colors[n], label=labels[n]) for n in colors]
    fig.legend(handles=legend_el, loc='lower center', ncol=3, fontsize=9, bbox_to_anchor=(0.5, 0.01))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.08, top=0.93, hspace=0.25, wspace=0.2)

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

    print("Arveles aranıyor...")
    ilac = veritabanindan_ilac_bilgisi_al("ARVELES")

    if not ilac:
        print("Ilac bulunamadi!")
        return

    print(f"Bulunan: {ilac['UrunAdi']}")
    print(f"  Depocu Fiyat: {ilac['DepocuFiyat']:.2f} TL")
    print(f"  Aylik Ort: {ilac['AylikOrt']:.1f} adet")
    print(f"  Stok: {ilac['Stok']} adet")

    sonuc = roi_bazli_hesapla(
        maliyet=ilac['DepocuFiyat'],
        aylik_ort=ilac['AylikOrt'],
        mevcut_stok=ilac['Stok'],
        zam_tarihi=ZAM_TARIHI,
        zam_orani=ZAM_ORANI,
        faiz_yillik=FAIZ_YILLIK,
        depo_vade=DEPO_VADE
    )

    if sonuc:
        kn = sonuc['kritik']
        print(f"\n{'='*60}")
        print("ROI BAZLI KRITIK NOKTALAR (Her 100 TL'de Kazanc)")
        print('='*60)
        print(f"  Maks ROI:    +{kn['max_roi']['m']} ad. => {kn['max_roi']['k']:,.0f} TL")
        print(f"               Yatirim: {kn['max_roi']['y']:,.0f} TL")
        print(f"               ROI: %{kn['max_roi']['r']:.2f} (Her 100 TL'de {kn['max_roi']['r']:.2f} TL kazanc)")
        print()
        print(f"  ROI %50:     +{kn['yarim_roi']['m']} ad. => %{kn['yarim_roi']['r']:.2f}")
        print(f"  Pareto %80:  +{kn['pareto']['m']} ad. => %{kn['pareto']['r']:.2f}")
        print(f"  Tepe (Pik):  +{kn['optimum']['m']} ad. => %{kn['optimum']['r']:.2f}")
        print(f"  ROI Sifir:   +{kn['sifir_roi']['m']} ad. => %{kn['sifir_roi']['r']:.2f}")

        roi_grafik_ciz(ilac, sonuc, ZAM_ORANI, ZAM_TARIHI, FAIZ_YILLIK, "zam_roi_arveles.png")


if __name__ == "__main__":
    main()
