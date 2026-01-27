import matplotlib.pyplot as plt
from datetime import date
import numpy as np

plt.rcParams['font.family'] = 'DejaVu Sans'

def hesapla_ve_ciz(urun_adi, maliyet, aylik_ort, mevcut_stok, zam_orani, zam_gun,
                   faiz_yillik, depo_vade, dosya_adi):

    aylik_faiz = (faiz_yillik / 100) / 12
    # Gün bazlı faiz hesabı için (daha smooth grafik)
    gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
    gunluk_sarf = aylik_ort / 30

    # Hesaplama
    adetler = list(range(0, 1500, 1))
    kazanclar = []

    for test_miktar in adetler:
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
                if gun < zam_gun:
                    fiyat = maliyet
                else:
                    fiyat = maliyet * (1 + zam_orani / 100)

                # Gün bazlı iskonto (smooth grafik için)
                # Ödeme: satış gününden 30 gün sonra fatura + depo_vade gün
                odeme_gun = gun + 30 + depo_vade
                odeme = yeni_harcanan * fiyat
                iskonto = (1 + gunluk_faiz) ** odeme_gun
                npv_aylik += odeme / iskonto
                kalan_yeni -= yeni_harcanan
            gun += 1

        # Toplu alımda: bugün alıyoruz, 30 + depo_vade gün sonra ödüyoruz
        npv_toplu = (test_miktar * maliyet) / ((1 + gunluk_faiz) ** (30 + depo_vade))
        kazanc = npv_aylik - npv_toplu
        kazanclar.append(kazanc)

    kazanclar = np.array(kazanclar)

    # Negatife dondugu nokta
    pozitif_mask = kazanclar > 0
    if pozitif_mask.any():
        maksimum_idx = np.where(pozitif_mask)[0][-1]
        maksimum_adet = adetler[maksimum_idx]
    else:
        maksimum_adet = len(adetler) - 1

    # Sadece pozitif bolgeyi al (+ biraz margin)
    goster_limit = min(maksimum_adet + 15, len(adetler) - 1)
    adetler_goster = adetler[:goster_limit+1]
    kazanclar_goster = kazanclar[:goster_limit+1]

    # Pik noktasi
    optimum_idx = np.argmax(kazanclar_goster)
    optimum_adet = adetler_goster[optimum_idx]
    optimum_kazanc = kazanclar_goster[optimum_idx]

    # Egim hesapla (1. turev)
    egim = np.gradient(kazanclar_goster)

    # Egimin degisimi (2. turev)
    egim_degisim = np.gradient(egim)

    # Plato noktasi - pikten sonra egimin %10'un altina dustugu yer
    max_egim = np.max(np.abs(egim[:optimum_idx+1])) if optimum_idx > 0 else 1
    plato_idx = optimum_idx
    for i in range(optimum_idx, len(egim)):
        if abs(egim[i]) < max_egim * 0.15:
            plato_idx = i
            break
    plato_adet = adetler_goster[plato_idx]
    plato_kazanc = kazanclar_goster[plato_idx]

    # Bukum noktasi (Inflection Point) - egimin en hizli azaldigi yer
    # 2. turev minimum oldugu nokta = azalan getiri basladigi yer
    if optimum_idx > 20:
        # Pikten onceki bolgeyi incele
        bolge_baslangic = 5
        bolge_bitis = optimum_idx
        egim_degisim_bolge = egim_degisim[bolge_baslangic:bolge_bitis]

        # 2. turev minimum (en negatif) = egim en hizli dusuyor
        bukum_idx_relatif = np.argmin(egim_degisim_bolge)
        bukum_idx = bolge_baslangic + bukum_idx_relatif
    else:
        bukum_idx = optimum_idx // 2
    bukum_adet = adetler_goster[bukum_idx]
    bukum_kazanc = kazanclar_goster[bukum_idx]

    # Negatife dondugu nokta
    negatif_adet = maksimum_adet
    negatif_kazanc = kazanclar[maksimum_adet]

    # PARETO NOKTASI - %80 kazanca ulaşılan nokta
    hedef_kazanc_80 = optimum_kazanc * 0.80
    pareto_idx = 0
    for i in range(len(kazanclar_goster)):
        if kazanclar_goster[i] >= hedef_kazanc_80:
            pareto_idx = i
            break
    pareto_adet = adetler_goster[pareto_idx]
    pareto_kazanc = kazanclar_goster[pareto_idx]

    # VERIMLILIK NOKTASI - Maksimum ROI (Kazanç / Yatırım)
    # Yatırım = test_miktar * maliyet
    roi_values = []
    for i, (adet, kazanc) in enumerate(zip(adetler_goster, kazanclar_goster)):
        if adet > 0:
            yatirim = adet * maliyet
            roi = kazanc / yatirim * 100  # Yüzde olarak
            roi_values.append((i, roi))
        else:
            roi_values.append((i, 0))

    max_roi_idx = max(roi_values, key=lambda x: x[1])[0]
    verimlilik_adet = adetler_goster[max_roi_idx]
    verimlilik_kazanc = kazanclar_goster[max_roi_idx]
    verimlilik_roi = roi_values[max_roi_idx][1]

    # Grafik
    fig, ax = plt.subplots(figsize=(16, 9))

    # Ana cizgi
    ax.plot(adetler_goster, kazanclar_goster, 'b-', linewidth=2.5, label='Kazanc (TL)')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=1)

    # Bolgeler
    ax.fill_between(adetler_goster, kazanclar_goster, 0,
                    where=(kazanclar_goster > 0), alpha=0.25, color='green', label='Karli Bolge')
    ax.fill_between(adetler_goster, kazanclar_goster, 0,
                    where=(kazanclar_goster <= 0), alpha=0.25, color='red', label='Zararli Bolge')

    # 1. Pik noktasi
    ax.scatter([optimum_adet], [optimum_kazanc], color='blue', s=300, zorder=5, marker='*')
    ax.annotate(f'PIK (Optimum)\n{optimum_adet} adet\n{optimum_kazanc:.0f} TL\n({(mevcut_stok+optimum_adet)/aylik_ort:.1f} ay)',
                xy=(optimum_adet, optimum_kazanc),
                xytext=(optimum_adet + goster_limit*0.1, optimum_kazanc * 0.8),
                fontsize=11, fontweight='bold', ha='left',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9),
                arrowprops=dict(arrowstyle='->', color='blue', lw=2))

    # 2. Verimlilik noktasi (maksimum ROI)
    ax.scatter([verimlilik_adet], [verimlilik_kazanc], color='green', s=200, zorder=5, marker='s')
    ax.annotate(f'MAX VERIMLILIK\n(ROI: %{verimlilik_roi:.1f})\n{verimlilik_adet} adet\n{verimlilik_kazanc:.0f} TL',
                xy=(verimlilik_adet, verimlilik_kazanc),
                xytext=(max(5, verimlilik_adet - goster_limit*0.08), verimlilik_kazanc + optimum_kazanc*0.35),
                fontsize=10, ha='right',
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9),
                arrowprops=dict(arrowstyle='->', color='green', lw=1.5))

    # 3. Pareto noktasi (%80 kazanc)
    ax.scatter([pareto_adet], [pareto_kazanc], color='orange', s=200, zorder=5, marker='^')
    ax.annotate(f'PARETO (%80)\n{pareto_adet} adet\n{pareto_kazanc:.0f} TL',
                xy=(pareto_adet, pareto_kazanc),
                xytext=(pareto_adet + goster_limit*0.08, pareto_kazanc - optimum_kazanc*0.15),
                fontsize=10, ha='left',
                bbox=dict(boxstyle='round', facecolor='moccasin', alpha=0.9),
                arrowprops=dict(arrowstyle='->', color='orange', lw=1.5))

    # 4. Büküm noktasi (azalan getiri) - plato yerine
    if bukum_adet != optimum_adet and bukum_adet < pareto_adet:
        ax.scatter([bukum_adet], [bukum_kazanc], color='purple', s=200, zorder=5, marker='D')
        ax.annotate(f'BUKUM\n(Azalan Getiri)\n{bukum_adet} adet\n{bukum_kazanc:.0f} TL',
                    xy=(bukum_adet, bukum_kazanc),
                    xytext=(bukum_adet + goster_limit*0.05, bukum_kazanc + optimum_kazanc*0.12),
                    fontsize=10, ha='left',
                    bbox=dict(boxstyle='round', facecolor='plum', alpha=0.9),
                    arrowprops=dict(arrowstyle='->', color='purple', lw=1.5))

    # 4. Sinir noktasi (negatife donus)
    ax.scatter([negatif_adet], [negatif_kazanc], color='red', s=200, zorder=5, marker='v')
    ax.annotate(f'SINIR\n{negatif_adet} adet\n({(mevcut_stok+negatif_adet)/aylik_ort:.1f} ay)',
                xy=(negatif_adet, negatif_kazanc),
                xytext=(negatif_adet - goster_limit*0.1, max(negatif_kazanc - optimum_kazanc*0.12, -optimum_kazanc*0.15)),
                fontsize=10, ha='right',
                bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.9),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5))

    # X ekseni 5'er 5'er
    max_x = ((goster_limit // 5) + 1) * 5
    ax.set_xticks(range(0, max_x + 1, 5))
    ax.set_xlim(-2, goster_limit + 5)

    # Y ekseni
    y_max = optimum_kazanc * 1.2
    y_min = min(min(kazanclar_goster) * 1.1, -optimum_kazanc * 0.1)
    ax.set_ylim(y_min, y_max)

    ax.set_xlabel('Yeni Alim Miktari (adet)', fontsize=13)
    ax.set_ylabel('Kazanc (TL)', fontsize=13)
    ax.set_title(f'{urun_adi}\n%{zam_orani} Zam, {zam_gun} Gun Sonra | Mevcut Stok: {mevcut_stok} | Aylik Sarf: {aylik_ort:.0f} | Faiz: %{faiz_yillik}',
                 fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)

    # Ozet kutusu
    info = f'''KARAR NOKTALARI:
  Max Verimlilik (ROI): {verimlilik_adet} adet ({(mevcut_stok+verimlilik_adet)/aylik_ort:.1f} ay) = {verimlilik_kazanc:.0f} TL [%{verimlilik_roi:.1f}]
  Pareto (%80): {pareto_adet} adet ({(mevcut_stok+pareto_adet)/aylik_ort:.1f} ay) = {pareto_kazanc:.0f} TL
  Pik (Optimum): {optimum_adet} adet ({(mevcut_stok+optimum_adet)/aylik_ort:.1f} ay) = {optimum_kazanc:.0f} TL
  Sinir: {negatif_adet} adet ({(mevcut_stok+negatif_adet)/aylik_ort:.1f} ay)'''

    ax.text(0.02, 0.97, info, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.95),
            family='monospace')

    plt.tight_layout()
    plt.savefig(dosya_adi, dpi=150, bbox_inches='tight')
    plt.close()

    print(f'{urun_adi}:')
    print(f'  Max Verimlilik: {verimlilik_adet} adet ({(mevcut_stok+verimlilik_adet)/aylik_ort:.1f} ay) = {verimlilik_kazanc:.0f} TL [ROI: %{verimlilik_roi:.1f}]')
    print(f'  Pareto (%80): {pareto_adet} adet ({(mevcut_stok+pareto_adet)/aylik_ort:.1f} ay) = {pareto_kazanc:.0f} TL')
    print(f'  Pik: {optimum_adet} adet ({(mevcut_stok+optimum_adet)/aylik_ort:.1f} ay) = {optimum_kazanc:.0f} TL')
    print(f'  Sinir: {negatif_adet} adet ({(mevcut_stok+negatif_adet)/aylik_ort:.1f} ay)')
    print(f'  Grafik: {dosya_adi}')
    print()

# Parametreler
zam_gun = 24  # 20 Subat
zam_orani = 17
faiz_yillik = 48
depo_vade = 75

# MAJEZIK
hesapla_ve_ciz(
    urun_adi='MAJEZIK 100MG 15 FILM TABLET',
    maliyet=125.07,
    aylik_ort=28.7,
    mevcut_stok=49,
    zam_orani=zam_orani,
    zam_gun=zam_gun,
    faiz_yillik=faiz_yillik,
    depo_vade=depo_vade,
    dosya_adi='zam_majezik.png'
)

# ARVELES
hesapla_ve_ciz(
    urun_adi='ARVELES 25MG 20 FILM TABLET',
    maliyet=73.02,
    aylik_ort=178.4,
    mevcut_stok=50,
    zam_orani=zam_orani,
    zam_gun=zam_gun,
    faiz_yillik=faiz_yillik,
    depo_vade=depo_vade,
    dosya_adi='zam_arveles.png'
)

print('Grafikler olusturuldu!')
