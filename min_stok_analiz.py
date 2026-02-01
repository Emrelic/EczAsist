"""
Minimum Stok Analizi Modulu
Bilimsel yontemler (Syntetos-Boylan) ve finansal basabas noktasi bazli minimum stok hesaplama
"""

import math
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


def talep_pattern_analiz(db, urun_id: int, ay_sayisi: int = 12) -> dict:
    """
    Bir ilacin talep pattern'ini analiz et

    Returns:
        dict: {
            'toplam_miktar': int,
            'talep_sayisi': int,      # Kac kez talep oldu
            'talep_gunleri': int,     # Kac gun talep vardi
            'aylik_ort': float,
            'ort_parti': float,       # Bir seferde kac adet
            'cv': float,              # Coefficient of Variation
            'adi': float,             # Average Demand Interval
            'sinif': str,             # SMOOTH/ERRATIC/INTERMITTENT/LUMPY
            'parti_std': float,       # Parti buyuklugu std sapma
        }
    """
    bugun = datetime.now()
    baslangic = (bugun - relativedelta(months=ay_sayisi)).strftime('%Y-%m-%d')
    toplam_gun = ay_sayisi * 30

    # Gunluk satis verileri
    sql = f"""
    SELECT
        CAST(ra.RxKayitTarihi AS DATE) as Tarih,
        SUM(ri.RIAdet) as Adet
    FROM ReceteIlaclari ri
    JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
    WHERE ri.RIUrunId = {urun_id}
    AND ra.RxSilme = 0 AND ri.RISilme = 0
    AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
    AND ra.RxKayitTarihi >= '{baslangic}'
    GROUP BY CAST(ra.RxKayitTarihi AS DATE)

    UNION ALL

    SELECT
        CAST(ea.RxKayitTarihi AS DATE) as Tarih,
        SUM(ei.RIAdet) as Adet
    FROM EldenIlaclari ei
    JOIN EldenAna ea ON ei.RIRxId = ea.RxId
    WHERE ei.RIUrunId = {urun_id}
    AND ea.RxSilme = 0 AND ei.RISilme = 0
    AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
    AND ea.RxKayitTarihi >= '{baslangic}'
    GROUP BY CAST(ea.RxKayitTarihi AS DATE)
    """

    try:
        gunluk_veriler = db.sorgu_calistir(sql)
    except Exception as e:
        logger.error(f"Talep analizi hatasi (UrunId={urun_id}): {e}")
        return None

    if not gunluk_veriler:
        return {
            'toplam_miktar': 0,
            'talep_sayisi': 0,
            'talep_gunleri': 0,
            'aylik_ort': 0,
            'ort_parti': 0,
            'cv': 0,
            'adi': 999,
            'sinif': 'NO_DEMAND',
            'parti_std': 0
        }

    # Tarihe gore birlestir (UNION'dan dolayi ayni gun 2 kez gelebilir)
    parti_dict = {}
    for v in gunluk_veriler:
        tarih = v['Tarih']
        adet = float(v['Adet'] or 0)
        if tarih in parti_dict:
            parti_dict[tarih] += adet
        else:
            parti_dict[tarih] = adet

    parti_buyuklukleri = list(parti_dict.values())

    # Istatistikler
    toplam_miktar = sum(parti_buyuklukleri)
    talep_sayisi = len(parti_buyuklukleri)
    talep_gunleri = len(parti_dict)
    ort_parti = toplam_miktar / talep_sayisi if talep_sayisi > 0 else 0
    aylik_ort = toplam_miktar / ay_sayisi

    # CV (Coefficient of Variation)
    if talep_sayisi > 1:
        ortalama = sum(parti_buyuklukleri) / len(parti_buyuklukleri)
        varyans = sum((x - ortalama)**2 for x in parti_buyuklukleri) / len(parti_buyuklukleri)
        std_sapma = math.sqrt(varyans)
        cv = std_sapma / ortalama if ortalama > 0 else 0
    else:
        std_sapma = 0
        cv = 0

    # ADI (Average Demand Interval) - gun bazinda
    adi = toplam_gun / talep_sayisi if talep_sayisi > 0 else 999

    # Syntetos-Boylan siniflandirmasi
    # Esik degerleri: CV = 0.49, ADI = 1.32
    if talep_sayisi == 0:
        sinif = 'NO_DEMAND'
    elif cv < 0.49 and adi < 1.32:
        sinif = 'SMOOTH'
    elif cv >= 0.49 and adi < 1.32:
        sinif = 'ERRATIC'
    elif cv < 0.49 and adi >= 1.32:
        sinif = 'INTERMITTENT'
    else:
        sinif = 'LUMPY'

    return {
        'toplam_miktar': toplam_miktar,
        'talep_sayisi': talep_sayisi,
        'talep_gunleri': talep_gunleri,
        'aylik_ort': aylik_ort,
        'ort_parti': ort_parti,
        'cv': cv,
        'adi': adi,
        'sinif': sinif,
        'parti_std': std_sapma
    }


def basabas_noktasi_hesapla(kar_marji: float, yillik_faiz: float) -> float:
    """
    Finansal basabas noktasi hesapla

    Args:
        kar_marji: Kar marji (0.25 = %25)
        yillik_faiz: Yillik faiz orani (0.45 = %45)

    Returns:
        float: Basabas noktasi (ay)
    """
    if kar_marji <= 0 or yillik_faiz <= 0:
        return 999

    aylik_faiz = yillik_faiz / 12
    basabas_ay = math.log(1 + kar_marji) / math.log(1 + aylik_faiz)
    return basabas_ay


def minimum_stok_hesapla(
    analiz: dict,
    kar_marji: float = 0.22,
    yillik_faiz: float = 0.40,
    tedarik_suresi: int = 1  # gun
) -> dict:
    """
    Minimum stok miktarini hesapla

    Args:
        analiz: talep_pattern_analiz() sonucu
        kar_marji: Ortalama kar marji
        yillik_faiz: Yillik mevduat faizi
        tedarik_suresi: Tedarik suresi (gun)

    Returns:
        dict: {
            'min_bilimsel': int,
            'min_finansal': int,
            'min_onerilen': int,
            'aciklama': str
        }
    """
    if not analiz or analiz['sinif'] == 'NO_DEMAND':
        return {
            'min_bilimsel': 0,
            'min_finansal': 0,
            'min_onerilen': 0,
            'aciklama': 'Talep yok'
        }

    sinif = analiz['sinif']
    ort_parti = analiz['ort_parti']
    aylik_ort = analiz['aylik_ort']
    gunluk_ort = aylik_ort / 30
    cv = analiz['cv']

    # Basabas noktasi
    basabas_ay = basabas_noktasi_hesapla(kar_marji, yillik_faiz)

    # ===== BILIMSEL YONTEM (Syntetos-Boylan) =====
    if sinif == 'LUMPY':
        # Cok duzensiz ve aralikli - siparis usulu
        min_bilimsel = 0
        aciklama_bilimsel = 'LUMPY: Siparis usulu'
    elif sinif == 'INTERMITTENT':
        # Aralikli ama duzensiz degil - parti buyuklugu kadar
        min_bilimsel = max(1, math.ceil(ort_parti))
        aciklama_bilimsel = f'INTERMITTENT: Parti={ort_parti:.1f}'
    elif sinif == 'ERRATIC':
        # Duzensiz ama surekli - emniyet payiyla
        min_bilimsel = max(2, math.ceil(ort_parti * (1 + cv)))
        aciklama_bilimsel = f'ERRATIC: Parti={ort_parti:.1f}, CV={cv:.2f}'
    else:  # SMOOTH
        # Duzgun talep - 1 haftalik stok
        min_bilimsel = max(1, math.ceil(aylik_ort / 4))
        aciklama_bilimsel = f'SMOOTH: 1 haftalik'

    # ===== FINANSAL YONTEM =====
    if aylik_ort < 1 / basabas_ay:
        # Yilda 1'den az - stok tutma zarar
        min_finansal = 0
        aciklama_finansal = f'Yillik<1, basabas={basabas_ay:.1f}ay'
    elif aylik_ort < basabas_ay:
        # Basabas altinda - minimum tut
        min_finansal = max(1, math.ceil(ort_parti))
        aciklama_finansal = f'Basabas altinda'
    else:
        # Basabas ustunde - rahat stok tutulabilir
        min_finansal = max(1, math.ceil(aylik_ort / 4))
        aciklama_finansal = f'Basabas ustunde'

    # ===== ONERILEN (her iki yontemin maksimumu) =====
    # Ama parti buyuklugunden az olamaz
    min_parti = math.ceil(ort_parti) if ort_parti > 0 else 0
    min_tedarik = math.ceil(gunluk_ort * tedarik_suresi)

    min_onerilen = max(
        min_bilimsel,
        min_finansal,
        min_parti,
        min_tedarik
    )

    # Ozel durumlar
    if sinif == 'LUMPY' and aylik_ort < 1:
        min_onerilen = 0  # Gercekten siparis usulu

    aciklama = f'{sinif} | Parti:{ort_parti:.1f} | {aciklama_finansal}'

    return {
        'min_bilimsel': min_bilimsel,
        'min_finansal': min_finansal,
        'min_onerilen': min_onerilen,
        'aciklama': aciklama
    }


def tum_ilaclari_analiz_et(
    db,
    ay_sayisi: int = 12,
    kar_marji: float = 0.22,
    yillik_faiz: float = 0.40,
    sadece_stoklu: bool = False,
    hareket_yili: int = 0,
    progress_callback=None
) -> list:
    """
    Tum ilaclari analiz et ve minimum stok onerisi olustur

    Args:
        db: Veritabani baglantisi
        ay_sayisi: Analiz donemi (ay)
        kar_marji: Ortalama kar marji
        yillik_faiz: Yillik mevduat faizi
        sadece_stoklu: Sadece stokta olan ilaclari analiz et
        hareket_yili: Son kac yil icinde hareket gormesi gerektigi (0=filtre yok)
        progress_callback: Ilerleme callback fonksiyonu (current, total)

    Returns:
        list: [{
            'UrunId': int,
            'UrunAdi': str,
            'MevcutMin': int,
            'Stok': int,
            'AylikOrt': float,
            'TalepSayisi': int,
            'OrtParti': float,
            'CV': float,
            'ADI': float,
            'Sinif': str,
            'MinBilimsel': int,
            'MinFinansal': int,
            'MinOnerilen': int,
            'Aciklama': str
        }, ...]
    """
    # Tum ilaclari getir
    stok_filtre = "AND (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0" if sadece_stoklu else ""

    # Hareket yili filtresi - son N yil icinde stok, satis veya alis hareketi olan ilaclar
    hareket_filtre = ""
    if hareket_yili > 0:
        hareket_ay = hareket_yili * 12
        bugun = datetime.now()
        hareket_baslangic = (bugun - relativedelta(months=hareket_ay)).strftime('%Y-%m-%d')
        hareket_filtre = f"""
        AND (
            -- Mevcut stoku var
            (COALESCE(u.UrunStokDepo,0) + COALESCE(u.UrunStokRaf,0) + COALESCE(u.UrunStokAcik,0)) > 0
            OR
            -- Karekod'da aktif stoku var
            EXISTS (SELECT 1 FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1)
            OR
            -- Son N yil icinde receteli satis yapmis
            EXISTS (
                SELECT 1 FROM ReceteIlaclari ri
                INNER JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
                WHERE ri.RIUrunId = u.UrunId
                AND ra.RxSilme = 0 AND ri.RISilme = 0
                AND ra.RxKayitTarihi >= '{hareket_baslangic}'
            )
            OR
            -- Son N yil icinde elden satis yapmis
            EXISTS (
                SELECT 1 FROM EldenIlaclari ei
                INNER JOIN EldenAna ea ON ei.RIRxId = ea.RxId
                WHERE ei.RIUrunId = u.UrunId
                AND ea.RxSilme = 0 AND ei.RISilme = 0
                AND ea.RxKayitTarihi >= '{hareket_baslangic}'
            )
        )
        """

    sql_ilaclar = f"""
    SELECT
        u.UrunId,
        u.UrunAdi,
        COALESCE(u.UrunMinimum, 0) as MevcutMin,
        CASE WHEN u.UrunUrunTipId IN (1, 16) THEN
            (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1)
        ELSE (COALESCE(u.UrunStokDepo,0) + COALESCE(u.UrunStokRaf,0) + COALESCE(u.UrunStokAcik,0))
        END as Stok
    FROM Urun u
    WHERE u.UrunSilme = 0
    AND u.UrunUrunTipId IN (1, 16)
    {stok_filtre}
    {hareket_filtre}
    ORDER BY u.UrunAdi
    """

    try:
        ilaclar = db.sorgu_calistir(sql_ilaclar)
    except Exception as e:
        logger.error(f"Ilac listesi hatasi: {e}")
        return []

    if not ilaclar:
        return []

    sonuclar = []
    toplam = len(ilaclar)

    for i, ilac in enumerate(ilaclar):
        urun_id = ilac['UrunId']

        # Progress callback
        if progress_callback and i % 50 == 0:
            progress_callback(i, toplam)

        # Talep analizi
        analiz = talep_pattern_analiz(db, urun_id, ay_sayisi)

        if not analiz:
            continue

        # Minimum stok hesapla
        min_sonuc = minimum_stok_hesapla(analiz, kar_marji, yillik_faiz)

        sonuclar.append({
            'UrunId': urun_id,
            'UrunAdi': ilac['UrunAdi'],
            'MevcutMin': ilac.get('MevcutMin', 0) or 0,
            'Stok': ilac.get('Stok', 0) or 0,
            'AylikOrt': round(analiz['aylik_ort'], 1),
            'TalepSayisi': analiz['talep_sayisi'],
            'OrtParti': round(analiz['ort_parti'], 1),
            'CV': round(analiz['cv'], 2),
            'ADI': round(analiz['adi'], 1),
            'Sinif': analiz['sinif'],
            'MinBilimsel': min_sonuc['min_bilimsel'],
            'MinFinansal': min_sonuc['min_finansal'],
            'MinOnerilen': min_sonuc['min_onerilen'],
            'Aciklama': min_sonuc['aciklama']
        })

    if progress_callback:
        progress_callback(toplam, toplam)

    return sonuclar


# ═══════════════════════════════════════════════════════════════════════════════
# UYARI: Botanik EOS veritabanina yazma KESINLIKLE YASAKTIR!
# Asagidaki fonksiyonlar DEVRE DISI BIRAKILMISTIR.
# Botanik EOS'a sadece SELECT sorgusu calistirmak serbesttir.
# INSERT, UPDATE, DELETE, ALTER, DROP vb. islemler YASAKTIR.
# ═══════════════════════════════════════════════════════════════════════════════

def veritabanina_min_stok_yaz(db, urun_id: int, min_stok: int) -> bool:
    """
    DEVRE DISI - Botanik EOS'a yazma yasak!

    Bu fonksiyon artik calismaz. Minimum stok degerleri
    sadece Excel'e aktarilabilir, Botanik EOS'a yazilamaz.
    """
    logger.warning(f"YASAK ISLEM: Botanik EOS'a yazma girisimi engellendi (UrunId={urun_id})")
    return False


def toplu_min_stok_guncelle(db, guncellemeler: list, progress_callback=None) -> tuple:
    """
    DEVRE DISI - Botanik EOS'a yazma yasak!

    Bu fonksiyon artik calismaz. Minimum stok degerleri
    sadece Excel'e aktarilabilir, Botanik EOS'a yazilamaz.
    """
    logger.warning(f"YASAK ISLEM: Botanik EOS'a toplu yazma girisimi engellendi ({len(guncellemeler)} kayit)")
    return (0, len(guncellemeler))  # Hepsi basarisiz
