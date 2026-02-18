"""
Zam Karlılık Grafiği v2 - Çoklu İlaç Karşılaştırma
Stok + Sipariş miktarının karlılığa etkisi

Mantık:
- Bu ay alınan ilaçlar bu ay satılırsa: finansman maliyeti yok
- Önümüzdeki aya sarkarsa: 1 ay erken ödeme = faiz maliyeti
- Zam öncesi alım: Ucuz aldığımız için kar
- Kar = Zam kazancı - Faiz maliyeti
- Sipariş arttıkça: artar -> plato -> düşer -> negatif (ters çan eğrisi)
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import numpy as np
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# Türkçe karakter desteği
plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


def veritabanindan_ilac_bilgisi_al(ilac_adi_parcasi: str):
    """Veritabanından ilaç bilgilerini çek"""
    try:
        from botanik_db import BotanikDB
        db = BotanikDB()
        if not db.baglan():
            print(f"Veritabani baglantisi kurulamadi!")
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
        WHERE u.UrunSilme = 0
        AND u.UrunAdi LIKE '%{ilac_adi_parcasi}%'
        AND u.UrunUrunTipId IN (1, 16)
        ORDER BY
            CASE WHEN u.UrunAdi LIKE '{ilac_adi_parcasi}%' THEN 0 ELSE 1 END,
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
            aylik_ort = toplam_cikis / 6

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
            print(f"'{ilac_adi_parcasi}' iceren ilac bulunamadi!")
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
    Zam öncesi alım karlılık hesabı.

    Mantık:
    - Senaryo A (Aylık alım): Her ay ihtiyaç kadar al, zamdan sonra yeni fiyattan al
    - Senaryo B (Toplu alım): Bugün toplu al, zam öncesi ucuz fiyattan

    Kar = NPV(Aylık alım) - NPV(Toplu alım)

    Aylık alımda zamdan sonra yüksek fiyat ödenir.
    Toplu alımda her şey ucuz alınır AMA erken ödeme yapılır (faiz maliyeti).

    Returns:
        dict with 'siparis_miktarlari', 'kazanclar', 'roi_ler', 'kritik_noktalar'
    """
    bugun = date.today()
    zam_gun = (zam_tarihi - bugun).days

    if zam_gun <= 0 or aylik_ort <= 0 or maliyet <= 0:
        return None

    # Gün bazlı faiz
    aylik_faiz = (faiz_yillik / 100) / 12
    gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
    gunluk_sarf = aylik_ort / 30

    # Test aralığı: 12 aylık
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

        # ===== SENARYO A: AYLIK ALIM NPV =====
        # Her gün ihtiyaç kadar harcanır
        # Zamdan önce ucuz, zamdan sonra pahalı fiyattan alım
        kalan_mevcut = mevcut_stok
        kalan_yeni = test_miktar
        npv_aylik = 0

        gun = 0
        while kalan_yeni > 0 and gun < 720:  # Max 2 yıl
            harcanan = gunluk_sarf

            # Önce mevcut stoktan harca (maliyet yok, zaten alınmış)
            mevcut_harcanan = min(kalan_mevcut, harcanan)
            kalan_mevcut -= mevcut_harcanan

            # Sonra yeni alımdan harca
            yeni_harcanan = min(harcanan - mevcut_harcanan, kalan_yeni)

            if yeni_harcanan > 0:
                # Fiyat: Zamdan önce mi sonra mı?
                if gun < zam_gun:
                    fiyat = maliyet
                else:
                    fiyat = maliyet * (1 + zam_orani / 100)

                # Ödeme: O ayın sonunda senet + 75 gün sonra ödeme
                # Ay sonu: ((gun // 30) + 1) * 30
                # Ödeme günü: Ay sonu + 30 (senet) + vade
                ay_sonu = ((gun // 30) + 1) * 30
                odeme_gun = ay_sonu + depo_vade

                # NPV'ye ekle
                odeme = yeni_harcanan * fiyat
                iskonto = (1 + gunluk_faiz) ** odeme_gun
                npv_aylik += odeme / iskonto

                kalan_yeni -= yeni_harcanan

            gun += 1

        # ===== SENARYO B: TOPLU ALIM NPV =====
        # Bugün toplu al, bu ayın sonunda senet, +75 gün sonra öde
        # Ödeme günü: 30 + depo_vade (bu ayın sonu + vade)
        npv_toplu = (test_miktar * maliyet) / ((1 + gunluk_faiz) ** (30 + depo_vade))

        # ===== KAZANÇ = NPV(Aylık) - NPV(Toplu) =====
        # Pozitif = Toplu almak avantajlı (zamdan kaçış karı > faiz maliyeti)
        kazanc = npv_aylik - npv_toplu

        siparis_miktarlari.append(test_miktar)
        kazanclar.append(kazanc)

        # ROI = Kazanç / Yatırım
        yatirim = test_miktar * maliyet
        roi = (kazanc / yatirim * 100) if yatirim > 0 else 0
        roi_ler.append(roi)

    # ===== MARJINAL KAZANÇ HESAPLA =====
    # Her +1 birim alımın getirdiği ek kazanç (TL/adet)
    marjinal_kazanclar = [0]  # İlk eleman için 0
    for i in range(1, len(kazanclar)):
        marjinal = kazanclar[i] - kazanclar[i-1]
        marjinal_kazanclar.append(marjinal)

    marjinal_array = np.array(marjinal_kazanclar)

    # ===== KRİTİK NOKTALAR =====
    kazanc_array = np.array(kazanclar)
    roi_array = np.array(roi_ler)

    # 1. OPTİMUM (Tepe) - Maksimum kazanç
    optimum_idx = np.argmax(kazanc_array)

    # 2. MAKSİMUM ROI (Verimlilik)
    roi_nonzero = roi_array.copy()
    roi_nonzero[0] = -999
    max_roi_idx = np.argmax(roi_nonzero)

    # 3. PARETO (%80 kazanç)
    pareto_hedef = kazanclar[optimum_idx] * 0.80
    pareto_idx = 0
    for i, k in enumerate(kazanclar):
        if k >= pareto_hedef:
            pareto_idx = i
            break

    # 4. NEGATİF DÖNÜŞ (Sınır) - Son pozitif nokta
    negatif_idx = 0
    for i, k in enumerate(kazanclar):
        if k > 0:
            negatif_idx = i
    # Bir sonraki nokta negatife döndüğü yer
    if negatif_idx < len(kazanclar) - 1:
        negatif_idx = negatif_idx + 1

    # 5. AZALAN VERİMLİLİK BAŞLANGICI
    # Marjinal kazancın maksimum olduğu nokta - bundan sonra her +1 birim daha az kazandırır
    # Pozitif marjinal değerlerin maksimumunu bul
    azalan_idx = 1
    max_marjinal = marjinal_kazanclar[1] if len(marjinal_kazanclar) > 1 else 0
    for i in range(2, len(marjinal_kazanclar)):
        if marjinal_kazanclar[i] > max_marjinal:
            max_marjinal = marjinal_kazanclar[i]
            azalan_idx = i

    # Marjinal kazancın yarıya düştüğü noktayı da bulalım (daha anlamlı olabilir)
    # Maksimum marjinalden %50 düşüş noktası
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
            'max_roi': {
                'miktar': siparis_miktarlari[max_roi_idx],
                'kazanc': kazanclar[max_roi_idx],
                'roi': roi_ler[max_roi_idx],
                'idx': max_roi_idx
            },
            'azalan_verim': {
                'miktar': siparis_miktarlari[azalan_yarim_idx],
                'kazanc': kazanclar[azalan_yarim_idx],
                'marjinal': marjinal_kazanclar[azalan_yarim_idx],
                'idx': azalan_yarim_idx
            },
            'pareto': {
                'miktar': siparis_miktarlari[pareto_idx],
                'kazanc': kazanclar[pareto_idx],
                'idx': pareto_idx
            },
            'optimum': {
                'miktar': siparis_miktarlari[optimum_idx],
                'kazanc': kazanclar[optimum_idx],
                'idx': optimum_idx
            },
            'negatif': {
                'miktar': siparis_miktarlari[negatif_idx],
                'kazanc': kazanclar[negatif_idx],
                'idx': negatif_idx
            }
        }
    }


def coklu_grafik_ciz(ilac_verileri: list, zam_orani: float, zam_tarihi: date,
                     faiz: float, dosya_adi: str = None):
    """Birden fazla ilaç için 2x2 grid karlılık grafikleri"""

    n_ilac = len(ilac_verileri)
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()

    zam_gun = (zam_tarihi - date.today()).days

    fig.suptitle(f"Zam Oncesi Siparis Karlilik Analizi\nZam: %{zam_orani} | {zam_gun} gun sonra | Faiz: %{faiz}",
                 fontsize=14, fontweight='bold', y=0.98)

    colors_nokta = {
        'max_roi': '#FF9800',      # Turuncu
        'azalan_verim': '#9C27B0', # Mor
        'pareto': '#4CAF50',       # Yeşil
        'optimum': '#2196F3',      # Mavi
        'negatif': '#F44336'       # Kırmızı
    }

    markers = {
        'max_roi': 'D',
        'azalan_verim': 'p',       # Pentagon
        'pareto': 's',
        'optimum': '^',
        'negatif': 'X'
    }

    labels_tr = {
        'max_roi': 'Maks. ROI',
        'azalan_verim': 'Azalan Verim',
        'pareto': 'Pareto (%80)',
        'optimum': 'Tepe (Maks. Kazanc)',
        'negatif': 'Negatife Donus'
    }

    for i, (ilac_bilgi, sonuc) in enumerate(ilac_verileri):
        if i >= 4:
            break

        ax = axes[i]

        miktarlar = sonuc['siparis_miktarlari']
        kazanclar = sonuc['kazanclar']
        kn = sonuc['kritik_noktalar']
        stok = sonuc['mevcut_stok']

        # Kar bölgesi (yeşil) ve zarar bölgesi (kırmızı)
        ax.fill_between(miktarlar, kazanclar, alpha=0.3, color='green',
                        where=[k >= 0 for k in kazanclar])
        ax.fill_between(miktarlar, kazanclar, alpha=0.3, color='red',
                        where=[k < 0 for k in kazanclar])

        # Kazanç eğrisi
        ax.plot(miktarlar, kazanclar, 'b-', linewidth=2, label='Kazanc Egrisi')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        # Mevcut stok çizgisi
        if stok > 0 and stok < max(miktarlar):
            ax.axvline(x=stok, color='purple', linestyle='--', linewidth=2, alpha=0.7)
            ax.text(stok, max(kazanclar) * 0.8, f' Stok:{stok}',
                   fontsize=8, color='purple', rotation=90, va='top')

        # Kritik noktaları işaretle
        for nokta_adi, nokta in kn.items():
            ax.scatter(nokta['miktar'], nokta['kazanc'],
                      c=colors_nokta[nokta_adi], s=120, marker=markers[nokta_adi],
                      zorder=5, edgecolors='black', linewidths=1)

            # Etiket
            offset_y = max(kazanclar) * 0.12 if max(kazanclar) > 0 else 100
            if nokta_adi == 'negatif':
                offset_y = -abs(offset_y)

            ax.annotate(
                f"{labels_tr[nokta_adi]}\n{nokta['miktar']} ad.\n{nokta['kazanc']:,.0f} TL",
                xy=(nokta['miktar'], nokta['kazanc']),
                xytext=(nokta['miktar'], nokta['kazanc'] + offset_y),
                fontsize=8, ha='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor=colors_nokta[nokta_adi], alpha=0.6),
                arrowprops=dict(arrowstyle='->', color='gray', lw=0.5)
            )

        # İlaç bilgisi kutusu
        bilgi = (f"Stok: {stok} ad.\n"
                f"Aylik: {ilac_bilgi['AylikOrt']:.0f} ad.\n"
                f"Fiyat: {ilac_bilgi['DepocuFiyat']:.1f} TL")
        ax.text(0.02, 0.98, bilgi, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # Başlık ve etiketler
        ilac_adi_kisalt = ilac_bilgi['UrunAdi'][:35] + "..." if len(ilac_bilgi['UrunAdi']) > 35 else ilac_bilgi['UrunAdi']
        ax.set_title(ilac_adi_kisalt, fontsize=11, fontweight='bold', pad=10)
        ax.set_xlabel('Siparis Miktari (adet)', fontsize=10)
        ax.set_ylabel('Net Kazanc (TL)', fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:,.0f}'))

    # Boş grafikleri gizle
    for i in range(len(ilac_verileri), 4):
        axes[i].axis('off')

    # Ortak legend
    legend_elements = [
        mpatches.Patch(color=colors_nokta['max_roi'], label='Maks. ROI (En verimli)'),
        mpatches.Patch(color=colors_nokta['azalan_verim'], label='Azalan Verim (Marjinal %50)'),
        mpatches.Patch(color=colors_nokta['pareto'], label='Pareto (%80 kazanc)'),
        mpatches.Patch(color=colors_nokta['optimum'], label='Tepe (Maks. mutlak kazanc)'),
        mpatches.Patch(color=colors_nokta['negatif'], label='Negatife Donus (Sinir)'),
        mpatches.Patch(color='gray', alpha=0.5, label='Mevcut Stok (dikey cizgi)'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=9,
               bbox_to_anchor=(0.5, 0.01))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.10, top=0.92, hspace=0.3)

    if dosya_adi:
        plt.savefig(dosya_adi, dpi=150, bbox_inches='tight')
        print(f"Grafik kaydedildi: {dosya_adi}")

    plt.close(fig)


def main():
    """Ana fonksiyon"""
    # Parametreler
    ZAM_ORANI = 25
    ZAM_TARIHI = date(2026, 3, 1)
    FAIZ_YILLIK = 45
    DEPO_VADE = 75

    ilaclar = [
        "MAJEZIK 100MG 15",
        "ARVELES",
        "KLOROBEN",
        "AMOKLAVIN BID 1000MG 10"
    ]

    ilac_verileri = []

    for ilac_adi in ilaclar:
        print(f"\n{'='*50}")
        print(f"Ilac: {ilac_adi}")
        print('='*50)

        ilac_bilgi = veritabanindan_ilac_bilgisi_al(ilac_adi)

        if ilac_bilgi is None:
            print(f"'{ilac_adi}' icin veri bulunamadi, atlaniyor...")
            continue

        print(f"Bulunan: {ilac_bilgi['UrunAdi']}")
        print(f"  Depocu Fiyat: {ilac_bilgi['DepocuFiyat']:.2f} TL")
        print(f"  Aylik Ort: {ilac_bilgi['AylikOrt']:.1f} adet")
        print(f"  Mevcut Stok: {ilac_bilgi['Stok']} adet")

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
            print("Karlilik hesaplanamadi!")
            continue

        kn = sonuc['kritik_noktalar']
        print(f"\nKritik Noktalar:")
        print(f"  Maks.ROI: {kn['max_roi']['miktar']} adet => {kn['max_roi']['kazanc']:,.0f} TL (ROI: %{kn['max_roi']['roi']:.1f})")
        print(f"  Azalan Verim: {kn['azalan_verim']['miktar']} adet => {kn['azalan_verim']['kazanc']:,.0f} TL (Marjinal: {kn['azalan_verim']['marjinal']:.2f} TL/ad)")
        print(f"  Pareto (%80): {kn['pareto']['miktar']} adet => {kn['pareto']['kazanc']:,.0f} TL")
        print(f"  Tepe (Optimum): {kn['optimum']['miktar']} adet => {kn['optimum']['kazanc']:,.0f} TL")
        print(f"  Negatife Donus: {kn['negatif']['miktar']} adet => {kn['negatif']['kazanc']:,.0f} TL")

        ilac_verileri.append((ilac_bilgi, sonuc))

    if ilac_verileri:
        coklu_grafik_ciz(ilac_verileri, ZAM_ORANI, ZAM_TARIHI, FAIZ_YILLIK,
                         "zam_karlilik_4ilac.png")
    else:
        print("\nHicbir ilac icin veri bulunamadi!")


if __name__ == "__main__":
    main()
